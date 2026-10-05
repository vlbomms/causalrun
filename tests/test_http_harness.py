"""Generic native preparation, operator scope, and actual stdio MCP reuse."""
import json
import os
import threading
import unittest
from urllib.error import HTTPError
from causalrun import native, storage
from causalrun.contracts import Rejected
from causalrun.server import create_server
from causalrun.transport import request
from tests import test_http_json
from tests.mcp_client import Client


class HTTPHarnessTests(unittest.TestCase):
    close_server = test_http_json.GenericHTTPTests.close_server

    def setUp(self):
        test_http_json.GenericHTTPTests.setUp(self)
        with storage.connect(self.path) as db:
            db.execute(native.BINDINGS)
        self.host = create_server(self.path, 0, 'generic-agent-token-long', 'unused-provider-token-long')
        self.host.RequestHandlerClass = native.NativeHandler
        self.host.operator_token = 'generic-operator-token-long'
        self.host.instance, self.host.github_author = 'generic-instance', None
        self.host.credential_operation = 'controlled.value.create.v1'
        self.worker_host = threading.Thread(target=self.host.serve_forever, daemon=True)
        self.worker_host.start()
        self.addCleanup(self.close_host)
        self.origin = 'http://127.0.0.1:' + str(self.host.server_port)
        self.fields = {'operation': 'http.json.write.v1', 'target': self.server.target, 'name': self.artifact['name']}
        from pathlib import Path
        self.state = Path(self.directory.name)
        native.private_json(self.state / 'capabilities.json', {'agent_token': 'generic-agent-token-long',
                                                             'operator_token': self.host.operator_token})
        native.private_json(self.state / 'service.json', {'url': self.origin, 'pid': os.getpid(), 'instance': self.host.instance})

    def close_host(self):
        self.host.shutdown()
        self.host.server_close()
        self.worker_host.join(5)

    def prepare(self, **overrides):
        fields = dict(self.fields, source=self.artifact['verifier']['source'], answers={}, contract=self.artifact)
        fields.update(overrides)
        return request(self.origin, '/native/prepare', 'generic-agent-token-long', fields)[1]

    def test_generic_first_use_and_shared_mcp_replay(self):
        lookup = request(self.origin, '/native/lookup', 'generic-agent-token-long', self.fields)[1]
        self.assertFalse(lookup['ready'])
        self.assertEqual(lookup['questions'], [])
        review = self.prepare()
        self.assertEqual(review['validation']['failed'], 0)
        with self.assertRaises(HTTPError) as error:
            request(self.origin, '/native/approve', 'generic-agent-token-long', {
                'connector_digest': review['connector_digest'], 'report_digest': review['report_digest'], 'scope': self.fields})
        self.assertEqual(error.exception.code, 401)
        self.assertEqual(self.server.writes, 0)
        request(self.origin, '/native/approve', self.host.operator_token, {
            'connector_digest': review['connector_digest'], 'report_digest': review['report_digest'], 'scope': self.fields})
        action = request(self.origin, '/v1/actions', 'generic-agent-token-long', {
            'connector_digest': review['connector_digest'], 'action_key': 'shared', 'payload': {'value': 'hello'}})[1]
        client = Client(self.state)
        try:
            replay = client.call('causalrun_write', dict(self.fields, action_key='shared', payload={'value': 'hello'}))
            self.assertFalse(replay['isError'])
            self.assertEqual(replay['structuredContent']['id'], action['id'])
            self.assertEqual(client.call('causalrun_result', {'action_id': action['id']})['structuredContent'], action)
        finally:
            client.close()
        self.assertEqual(self.server.writes, 1)
        self.assertEqual(len(self.server.objects), 1)

    def test_ambiguous_intent_requires_answer(self):
        lookup = native.binding(self.path, dict(self.fields, needs_success_clarification=True))
        self.assertEqual(len(lookup['questions']), 1)
        with self.assertRaises(HTTPError):
            self.prepare(needs_success_clarification=True)
        review = self.prepare(needs_success_clarification=True, answers={'expected_behavior': 'Exact client ID and value'})
        self.assertEqual(review['artifact']['expected'], 'Exact client ID and value')
        self.assertEqual(self.server.writes, 0)

    def test_changed_scope_cannot_prepare_or_approve(self):
        with self.assertRaises(HTTPError):
            self.prepare(name='another-operation')
        review = self.prepare()
        with self.assertRaises(HTTPError):
            request(self.origin, '/native/approve', self.host.operator_token, {
                'connector_digest': review['connector_digest'], 'report_digest': review['report_digest'],
                'scope': dict(self.fields, name='another-operation')})
        self.assertEqual(self.server.writes, 0)

    def test_unsupported_transport_is_blocked(self):
        for target in ('http://external.example', 'ftp://example.com', 'https://example.com/path'):
            with self.subTest(target=target), self.assertRaises(Rejected):
                native.scope(dict(self.fields, target=target))
