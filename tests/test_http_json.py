"""Generic adapter checks against two independent local JSON API shapes."""
import copy
import json
import os
import socket
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote, urlsplit
from causalrun import runtime, storage, validation
from causalrun.contracts import Rejected, check_artifact, digest, implementation_digest
from causalrun.http_json import call, prepare_request


def artifact(target, shape='entry'):
    field = 'entry' if shape == 'entry' else 'record'
    return {
        'schema_version': 4, 'name': 'fixture-' + shape, 'version': 1,
        'target': target, 'operation': 'http.json.write.v1', 'api_version': 'fixture-1',
        'expected': 'A record with this client ID and exact value exists',
        'verifier': {'kind': 'python.receipt.v1', 'source':
            'def verify(action_id, payload, evidence):\n'
            '    return isinstance(evidence, dict) and isinstance(evidence["' + field + '"], dict) '
            'and evidence["' + field + '"]["client_id"] == action_id '
            'and evidence["' + field + '"]["value"] == payload["value"]\n'},
        'adapter': {
            'write': {'method': 'POST' if shape == 'entry' else 'PUT',
                      'path': ['entries'] if shape == 'entry' else ['records', {'$bind': 'action_id'}],
                      'query': {}, 'headers': {}, 'statuses': [201],
                      'body': {'client_id': {'$bind': 'action_id'},
                               'value': {'$bind': 'payload', 'path': ['value']}}},
            'read': {'method': 'GET', 'path': ['entries' if shape == 'entry' else 'records', {'$bind': 'action_id'}],
                     'query': {}, 'headers': {}, 'statuses': [200]}},
        'authentication': {'write': {'type': 'bearer', 'secret': 'TEST_WRITE_TOKEN'},
                           'read': {'type': 'api_key', 'secret': 'TEST_READ_TOKEN', 'header': 'X-Read-Key'}},
        'fixture': {'payload': {'value': 'hello'}, 'different_payload': {'value': 'other'},
                    'evidence': {field: {'client_id': {'$bind': 'action_id'}, 'value': 'hello'}}},
        'limitations': ['Missing evidence does not prove non-execution', 'Fixture checks do not prove provider guarantees'],
        'sources': ['tests/test_http_json.py: controlled application contract'],
        'implementation': implementation_digest()}


def provider():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, value):
            data = json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def write(self):
            self.server.writes += 1
            if self.headers.get('Authorization') != 'Bearer disposable-write-secret':
                return self.respond(403, {})
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            path = urlsplit(self.path).path
            shape = 'entry' if self.command == 'POST' and path == '/entries' else 'record'
            if shape == 'record' and (self.command != 'PUT' or path != '/records/' + body['client_id']):
                return self.respond(400, {})
            self.server.objects[(shape, body['client_id'])] = body
            if self.server.fault == 'drop_response':
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            if self.server.fault == 'bad_receipt':
                return self.respond(201, {shape: {'client_id': 'wrong', 'value': body['value']}})
            self.respond(201, {shape: body})

        do_POST = write
        do_PUT = write

        def do_GET(self):
            if self.path == '/openapi.json':
                return self.respond(200, {'openapi': '3.0.3', 'info': {'title': 'Generic entry fixture', 'version': 'fixture-1'},
                    'paths': {'/entries': {'post': {'operationId': 'createEntry',
                        'description': 'Create one entry with client_id and value. GET /entries/{client_id} returns the entry.',
                        'responses': {'201': {'description': 'JSON entry with the exact client_id and value'}}}},
                        '/entries/{client_id}': {'get': {'operationId': 'getEntry',
                            'responses': {'200': {'description': 'JSON entry'}, '404': {'description': 'No visible entry; not proof of failed write'}}}}}})
            self.server.reads += 1
            if self.headers.get('X-Read-Key') != 'disposable-read-secret':
                return self.respond(403, {})
            path = urlsplit(self.path).path
            if path.startswith('/redirect/'):
                self.send_response(302)
                self.send_header('Location', self.server.target + '/entries/elsewhere')
                self.end_headers()
                return
            if path.startswith('/oversized/'):
                return self.respond(200, {'value': 'x' * 65537})
            if path.startswith('/secret/'):
                return self.respond(200, {'value': 'disposable-read-secret'})
            if path.startswith('/list/'):
                from urllib.parse import parse_qs
                page = int(parse_qs(urlsplit(self.path).query)['page'][0])
                size = int(parse_qs(urlsplit(self.path).query)['limit'][0])
                start = (page - 1) * size
                return self.respond(200, self.server.listing[start:start + size])
            parts = path.split('/')
            shape = 'entry' if parts[1] == 'entries' else 'record'
            item = self.server.objects.get((shape, unquote(parts[-1])))
            if self.server.evidence == 'missing':
                item = None
            elif self.server.evidence == 'wrong' and item:
                item = dict(item, value='misleading value')
            elif self.server.evidence == 'unavailable':
                return self.respond(503, {})
            self.respond(200 if item else 404, {shape: item})
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.writes, server.reads, server.objects = 0, 0, {}
    server.fault, server.evidence, server.listing = None, None, []
    server.target = 'http://127.0.0.1:' + str(server.server_port)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    return server, worker


class GenericHTTPTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = str(Path(self.directory.name) / 'runtime.sqlite')
        storage.initialize(self.path)
        self.server, self.worker = provider()
        self.addCleanup(self.close_server)
        self.env = patch.dict(os.environ, {'TEST_WRITE_TOKEN': 'disposable-write-secret',
                                          'TEST_READ_TOKEN': 'disposable-read-secret'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.artifact = artifact(self.server.target)

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(5)

    def approved(self, value=None):
        value = value or self.artifact
        identifier = runtime.register(self.path, value)
        report = validation.validate(self.path, identifier)
        self.assertEqual(report['failed'], 0)
        runtime.approve(self.path, identifier, identifier, digest(report))
        return identifier

    def test_two_api_shapes_without_provider_specific_runtime(self):
        for shape in ('entry', 'record'):
            identifier = self.approved(artifact(self.server.target, shape))
            action = runtime.execute(self.path, identifier, 'shape/' + shape, {'value': 'hello'}, '')
            self.assertEqual(action['state'], 'COMMITTED')
            self.assertEqual(action['receipt'][shape]['client_id'], action['id'])
            self.assertEqual(self.server.objects[(shape, action['id'])]['value'], 'hello')
        self.assertEqual(self.server.writes, 2)
        self.assertEqual(len(self.server.objects), 2)

    def test_unvalidated_write_is_blocked(self):
        identifier = runtime.register(self.path, self.artifact)
        with self.assertRaises(Rejected):
            runtime.execute(self.path, identifier, 'blocked', {'value': 'hello'}, '')
        self.assertEqual(self.server.writes, 0)

    def test_unapproved_write_is_blocked(self):
        identifier = runtime.register(self.path, self.artifact)
        validation.validate(self.path, identifier)
        with self.assertRaises(Rejected):
            runtime.execute(self.path, identifier, 'blocked', {'value': 'hello'}, '')
        self.assertEqual(self.server.writes, 0)

    def test_repeat_and_result_make_no_provider_calls(self):
        identifier = self.approved()
        first = runtime.execute(self.path, identifier, 'same', {'value': 'hello'}, '')
        del os.environ['TEST_WRITE_TOKEN']
        del os.environ['TEST_READ_TOKEN']
        again = runtime.execute(self.path, identifier, 'same', {'value': 'hello'}, '')
        self.assertEqual(first, again)
        self.assertEqual(runtime.result(self.path, first['id']), first)
        self.assertEqual(self.server.writes, 1)
        self.assertEqual(self.server.reads, 0)

    def test_changed_payload_rejected(self):
        identifier = self.approved()
        runtime.execute(self.path, identifier, 'same', {'value': 'hello'}, '')
        with self.assertRaises(Rejected):
            runtime.execute(self.path, identifier, 'same', {'value': 'other'}, '')
        self.assertEqual(self.server.writes, 1)

    def test_missing_credentials_leave_no_authorization(self):
        identifier = self.approved()
        del os.environ['TEST_READ_TOKEN']
        with self.assertRaises(Rejected):
            runtime.execute(self.path, identifier, 'missing', {'value': 'hello'}, '')
        with storage.connect(self.path) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM actions').fetchone()[0], 0)
        self.assertEqual(self.server.writes, 0)

    def test_bindings_cannot_escape_origin(self):
        self.artifact['adapter']['read']['path'] = ['lookup', {'$bind': 'payload', 'path': ['value']}]
        self.artifact['adapter']['read']['query'] = {'q': {'$bind': 'payload', 'path': ['value']}}
        request = prepare_request(self.artifact, 'read', 'a', {'value': 'https://evil.example/a?b=1#c'})
        self.assertEqual(urlsplit(request.full_url).netloc, urlsplit(self.server.target).netloc)
        self.assertIn('https%3A%2F%2Fevil.example', request.full_url)

    def test_bad_origins_rejected(self):
        for target in ('http://example.com', 'https://x.example/path', 'https://user:pass@x.example',
                       'https://x.example?foo=bar', 'https://x.example#fragment', '//x.example', 'https://x.example:bad'):
            with self.subTest(target=target), self.assertRaises(Rejected):
                value = copy.deepcopy(self.artifact)
                value['target'] = target
                check_artifact(value)

    def test_unsafe_headers_rejected(self):
        for header, value in [('Host', 'evil.example'), ('Authorization', 'secret'),
                              ('Cookie', 'a=b'), ('X-Test', 'ok\r\nInjected: yes')]:
            with self.subTest(header=header), self.assertRaises(Rejected):
                candidate = copy.deepcopy(self.artifact)
                candidate['adapter']['write']['headers'] = {header: value}
                check_artifact(candidate)

    def test_invalid_bindings_rejected(self):
        for item in ({'$bind': 'environment'}, {'$bind': 'payload', 'path': []},
                     {'$bind': 'payload', 'path': ['absent']}, '..'):
            with self.subTest(item=item), self.assertRaises(Rejected):
                candidate = copy.deepcopy(self.artifact)
                candidate['adapter']['read']['path'] = ['lookup', item]
                check_artifact(candidate)

    def test_mutating_evidence_request_rejected(self):
        self.artifact['adapter']['read']['method'] = 'POST'
        with self.assertRaises(Rejected):
            check_artifact(self.artifact)

    def test_redirect_is_not_followed(self):
        self.artifact['adapter']['read']['path'] = ['redirect', {'$bind': 'action_id'}]
        with self.assertRaises(Exception):
            call(self.artifact, 'read', 'test', {'value': 'hello'})
        self.assertEqual(self.server.reads, 1)

    def test_response_size_is_bounded(self):
        self.artifact['adapter']['read']['path'] = ['oversized', {'$bind': 'action_id'}]
        with self.assertRaises(Rejected):
            call(self.artifact, 'read', 'test', {'value': 'hello'})

    def test_reflected_secret_is_not_returned(self):
        self.artifact['adapter']['read']['path'] = ['secret', {'$bind': 'action_id'}]
        with self.assertRaises(Rejected) as raised:
            call(self.artifact, 'read', 'test', {'value': 'hello'})
        self.assertNotIn('disposable-read-secret', str(raised.exception))

    def test_always_true_verifier_fails_validation(self):
        self.artifact['verifier']['source'] = 'def verify(action_id, payload, evidence):\n    return True\n'
        identifier = runtime.register(self.path, self.artifact)
        report = validation.validate(self.path, identifier)
        self.assertEqual(report['failed'], 3)
        with self.assertRaises(Rejected):
            runtime.approve(self.path, identifier, identifier, digest(report))

    def test_no_auth_requires_no_secret(self):
        self.artifact['authentication']['read'] = {'type': 'none'}
        request = prepare_request(self.artifact, 'read', 'test', {'value': 'hello'})
        self.assertNotIn('Authorization', request.headers)
        self.assertNotIn('X-read-key', request.headers)
