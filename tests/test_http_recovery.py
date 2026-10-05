"""Deterministic JSON recovery faults, bounded listings, and process crashes."""
import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from urllib.error import URLError
from causalrun import runtime, storage
from causalrun.contracts import Rejected
from causalrun.http_json import call
from causalrun.transport import request
from causalrun.verifiers import confirms
from tests import test_http_json
from tests.test_http_json import artifact

ROOT = Path(__file__).resolve().parents[1]
SCHEDULES = []


class HTTPRecoveryTests(unittest.TestCase):
    setUp = test_http_json.GenericHTTPTests.setUp
    close_server = test_http_json.GenericHTTPTests.close_server
    approved = test_http_json.GenericHTTPTests.approved

    def test_lost_response_missing_wrong_unavailable_then_recovered(self):
        identifier = self.approved()
        self.server.fault = 'drop_response'
        action = runtime.execute(self.path, identifier, 'lost', {'value': 'hello'}, '')
        self.assertEqual(action['state'], 'IN_DOUBT')
        for mode in ('missing', 'wrong', 'unavailable'):
            self.server.evidence = mode
            self.assertEqual(runtime.verify(self.path, action['id'], '')['state'], 'IN_DOUBT')
            self.assertEqual(runtime.execute(self.path, identifier, 'lost', {'value': 'hello'}, '')['id'], action['id'])
        self.server.evidence = None
        recovered = runtime.verify(self.path, action['id'], '')
        self.assertEqual(recovered['state'], 'COMMITTED')
        self.assertEqual(self.server.writes, 1)
        self.assertEqual(len(self.server.objects), 1)
        self.assertEqual(self.server.reads, 4)
        SCHEDULES.append({'schedule': 'commit/drop response; missing/wrong/unavailable evidence; visible evidence',
                          'action': recovered, 'writes': 1, 'objects': 1, 'reads': 4})

    def test_bad_immediate_receipt_requires_read(self):
        identifier = self.approved()
        self.server.fault = 'bad_receipt'
        action = runtime.execute(self.path, identifier, 'bad-response', {'value': 'hello'}, '')
        self.assertEqual(action['state'], 'IN_DOUBT')
        self.assertEqual(runtime.verify(self.path, action['id'], '')['state'], 'COMMITTED')
        self.assertEqual(self.server.writes, 1)

    def listing_contract(self, limit=3):
        value = copy.deepcopy(self.artifact)
        value['adapter']['read']['path'] = ['list', {'$bind': 'action_id'}]
        value['adapter']['read']['pagination'] = {'page': 'page', 'size': 'limit', 'page_size': 2, 'limit': limit}
        return value

    def test_bounded_pagination_collects_all_pages(self):
        value = self.listing_contract()
        self.server.listing = [{'id': '1'}, {'id': '2'}, {'id': '3'}]
        self.assertEqual(call(value, 'read', 'id', {'value': 'hello'}), self.server.listing)
        self.assertEqual(self.server.reads, 2)

    def test_page_limit_blocks_partial_positive_evidence(self):
        value = self.listing_contract(limit=1)
        self.server.listing = [{'id': '1'}, {'id': '2'}]
        with self.assertRaises(Rejected):
            call(value, 'read', 'id', {'value': 'hello'})
        self.assertEqual(self.server.reads, 1)

    def test_unique_match_conflicts_never_confirm(self):
        source = ('def verify(action_id, payload, evidence):\n'
                  '    return isinstance(unique_match(evidence, "client_id", action_id), dict) '
                  'and unique_match(evidence, "client_id", action_id)["value"] == payload["value"]\n')
        item = {'client_id': 'id', 'value': 'hello'}
        self.assertTrue(confirms(source, 'id', {'value': 'hello'}, [item]))
        self.assertFalse(confirms(source, 'id', {'value': 'hello'}, [item, item]))
        self.assertFalse(confirms(source, 'id', {'value': 'hello'}, []))
        self.assertFalse(confirms(source, 'id', {'value': 'other'}, [item]))

    def test_marker_template_is_bound_before_write(self):
        value = artifact(self.server.target)
        value['adapter']['write']['body']['value'] = {'$text': [
            {'$bind': 'payload', 'path': ['value']}, '\nmarker:', {'$bind': 'action_id'}]}
        from causalrun.http_json import prepare_request
        built = prepare_request(value, 'write', 'id', {'value': 'hello'})
        self.assertEqual(json.loads(built.data)['value'], 'hello\nmarker:id')

    def test_four_process_boundaries(self):
        for phase in ('before_authorization_commit', 'after_authorization_commit',
                      'after_provider_commit', 'after_receipt_commit'):
            with self.subTest(phase=phase):
                value = artifact(self.server.target)
                value['name'] = 'boundary-' + phase
                identifier = self.approved(value)
                env = dict(os.environ, CAUSALRUN_AGENT_TOKEN='boundary-agent-token-long',
                           CAUSALRUN_PROVIDER_TOKEN='boundary-write-token-long',
                           CAUSALRUN_RECEIPT_TOKEN='boundary-read-token-long')
                process = subprocess.Popen([sys.executable, '-m', 'tests.crash_runtime', '--db', self.path, '--phase', phase],
                                           cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    address = json.loads(process.stdout.readline())['listening']
                    origin = 'http://127.0.0.1:' + str(address[1])
                    before = self.server.writes
                    try:
                        request(origin, '/v1/actions', env['CAUSALRUN_AGENT_TOKEN'],
                                {'connector_digest': identifier, 'action_key': phase, 'payload': {'value': 'hello'}})
                    except (OSError, URLError):
                        pass
                    self.assertEqual(process.wait(10), 71)
                    with storage.connect(self.path) as db:
                        rows = db.execute('SELECT id,state FROM actions WHERE connector_digest=?', (identifier,)).fetchall()
                    if phase == 'before_authorization_commit':
                        self.assertEqual(len(rows), 0)
                        self.assertEqual(self.server.writes, before)
                        action = runtime.execute(self.path, identifier, phase, {'value': 'hello'}, '')
                        self.assertEqual(action['state'], 'COMMITTED')
                    else:
                        self.assertEqual(len(rows), 1)
                        action = runtime.execute(self.path, identifier, phase, {'value': 'hello'}, '')
                        self.assertEqual(self.server.writes - before, 0 if phase == 'after_authorization_commit' else 1)
                        action = runtime.verify(self.path, action['id'], '')
                        self.assertEqual(action['state'], 'IN_DOUBT' if phase == 'after_authorization_commit' else 'COMMITTED')
                    SCHEDULES.append({'schedule': phase, 'process_exit': 71, 'action': action,
                                      'writes_after_schedule': self.server.writes - before,
                                      'objects_total': len(self.server.objects)})
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait(5)
                    process.stdout.close()
                    process.stderr.close()
