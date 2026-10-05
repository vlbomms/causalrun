"""MCP lifecycle, strict inputs, and the shared runtime's fault boundary."""
import json
import tempfile
import unittest
import os
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from causalrun import mcp, native, storage
from causalrun.transport import request
from tests import test_gate4
from tests.mcp_client import Client
from tests.test_gate1 import terminal_approval

FAULT_RESULTS = []


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.adapter = mcp.Adapter('/tmp/unused-causalrun-test')

    def send(self, method, params=None, identifier=1):
        return self.adapter.process(json.dumps({'jsonrpc': '2.0', 'id': identifier, 'method': method, 'params': params or {}}))

    def initialize(self):
        self.send('initialize', {'protocolVersion': '2025-11-25', 'capabilities': {}, 'clientInfo': {'name': 'test'}})
        self.adapter.process('{"jsonrpc":"2.0","method":"notifications/initialized"}')

    def test_initialization_and_optional_tool_metadata(self):
        self.assertEqual(self.send('tools/list')['error']['code'], -32600)
        self.initialize()
        tools = self.send('tools/list', {'_meta': {'client': 'codex'}, 'cursor': None})['result']['tools']
        self.assertEqual(len(tools), 5)
        self.assertFalse(any('approve' in tool['name'] for tool in tools))
        self.assertEqual(self.send('tools/list', {'cursor': 'unknown'})['error']['code'], -32602)

    def test_invalid_frames_and_unknown_methods(self):
        self.assertEqual(self.adapter.process('{')['error']['code'], -32700)
        self.assertEqual(self.adapter.process('[]')['error']['code'], -32600)
        self.assertEqual(self.adapter.process('x' * 16385)['error']['code'], -32600)
        self.assertIsNone(self.send('ping', identifier=True)['id'])
        self.initialize()
        self.assertEqual(self.send('approve')['error']['code'], -32601)

    def test_notifications_cannot_dispatch(self):
        self.initialize()
        with patch.object(self.adapter, 'api') as api:
            self.assertIsNone(self.adapter.process(json.dumps({'jsonrpc': '2.0', 'method': 'tools/call',
                              'params': {'name': 'causalrun_write', 'arguments': {}}})))
            api.assert_not_called()

    def test_strict_tool_fields_and_secret_safe_errors(self):
        self.initialize()
        for arguments in ({'action_id': 1}, {'action_id': 'x', 'approved': True}):
            response = self.send('tools/call', {'name': 'causalrun_result', 'arguments': arguments})
            self.assertEqual(response['error']['code'], -32602)
        with patch.object(self.adapter, 'api', side_effect=RuntimeError('secret-provider-token')):
            result = self.send('tools/call', {'name': 'causalrun_result', 'arguments': {'action_id': 'x'}})
            self.assertTrue(result['result']['isError'])
            self.assertNotIn('secret-provider-token', json.dumps(result))

    def test_actual_stdio_handshake(self):
        with tempfile.TemporaryDirectory() as state:
            client = Client(state)
            try:
                self.assertEqual(len(client.request('tools/list', {'_meta': {}})['result']['tools']), 5)
                self.assertEqual(client.request('ping')['result'], {})
                self.assertIn('error', client.request('tools/call', {'name': 'causalrun_approve', 'arguments': {}}))
            finally:
                client.close()


class AdapterRuntimeTests(unittest.TestCase):
    setUp = test_gate4.NativeTests.setUp
    tearDown = test_gate4.NativeTests.tearDown
    prepare = test_gate4.NativeTests.prepare

    def adapter(self):
        adapter = mcp.Adapter(self.folder)
        adapter.api = lambda path, body=None: request(self.url, path, 'native-agent-token-long', body)[1]
        return adapter

    def approve(self, review):
        request(self.url, '/native/approve', self.server.operator_token, {
            'connector_digest': review['connector_digest'], 'report_digest': review['report_digest'], 'scope': self.fields})

    def test_unapproved_and_bad_verifiers_never_send(self):
        adapter = self.adapter()
        arguments = dict(self.fields, action_key='held', payload={'value': 'test'})
        self.assertEqual(adapter.call('causalrun_write', arguments)['structuredContent']['status'], 'PREPARATION_REQUIRED')
        bad = adapter.call('causalrun_prepare', dict(self.fields, source='def verify(action_id, payload, evidence):\n    return True\n',
                           api_version='1', answers={'expected_behavior': 'Exact value', 'sandbox': 'Yes, only the disposable fixture', 'unknown_policy': 'Keep blocked and request review'}))
        self.assertEqual(bad['structuredContent']['status'], 'VALIDATION_FAILED')
        self.assertNotIn('operator_token', json.dumps(bad))
        with storage.connect(self.provider.db_path) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM requests').fetchone()[0], 0)

    def test_lost_response_reuses_action_and_durable_result(self):
        self.approve(self.prepare())
        adapter = self.adapter(); self.provider.fault_mode = 'drop_response'
        arguments = dict(self.fields, action_key='same-key', payload={'value': 'test'})
        original = adapter.call('causalrun_write', arguments)['structuredContent']
        self.assertEqual(original['state'], 'IN_DOUBT')
        repeated = self.adapter().call('causalrun_write', arguments)['structuredContent']
        self.assertEqual(repeated['id'], original['id'])
        self.assertEqual(repeated['state'], 'IN_DOUBT')
        changed = adapter.call('causalrun_write', dict(arguments, payload={'value': 'changed'}))
        self.assertTrue(changed['isError'])
        confirmed = adapter.call('causalrun_verify', {'action_id': original['id']})['structuredContent']
        self.assertEqual(confirmed['state'], 'COMMITTED')
        self.assertEqual(adapter.call('causalrun_result', {'action_id': original['id']})['structuredContent']['state'], 'COMMITTED')
        with storage.connect(self.provider.db_path) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM requests').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM values_and_receipts').fetchone()[0], 1)

    def test_operator_review_requires_terminal(self):
        with patch('sys.stdin.isatty', return_value=False):
            with self.assertRaises(native.Rejected): native.review(self.folder, 'not-approved')

    def test_missing_misleading_and_unavailable_evidence(self):
        self.approve(self.prepare()); adapter = self.adapter()
        for fault in ('missing_receipt', 'wrong_action', 'wrong_payload', 'wrong_value', 'verifier_error'):
            self.provider.fault_mode = 'drop_response'
            arguments = dict(self.fields, action_key=fault, payload={'value': 'test'})
            action = adapter.call('causalrun_write', arguments)['structuredContent']
            self.assertEqual(action['state'], 'IN_DOUBT')
            self.provider.fault_mode = fault
            checked = adapter.call('causalrun_verify', {'action_id': action['id']})['structuredContent']
            self.assertEqual(checked['state'], 'IN_DOUBT')
            self.assertEqual(self.adapter().call('causalrun_write', arguments)['structuredContent']['id'], action['id'])
            self.provider.fault_mode = 'none'
            recovered = adapter.call('causalrun_verify', {'action_id': action['id']})['structuredContent']
            self.assertEqual(recovered['state'], 'COMMITTED')
            with storage.connect(self.provider.db_path) as db:
                count = db.execute('SELECT count(*) FROM requests WHERE action_id=?', (action['id'],)).fetchone()[0]
                objects = db.execute('SELECT count(*) FROM values_and_receipts WHERE action_id=?', (action['id'],)).fetchone()[0]
            self.assertEqual(count, 1)
            self.assertEqual(objects, 1)
            FAULT_RESULTS.append({'fault': fault, 'uncertain': checked, 'recovered': recovered, 'provider_posts': count, 'provider_objects': objects})

    def test_delayed_commit_does_not_authorize_replacement(self):
        self.approve(self.prepare()); adapter = self.adapter()
        self.provider.fault_mode = 'delay_commit'
        arguments = dict(self.fields, action_key='delayed', payload={'value': 'later'})
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(adapter.call, 'causalrun_write', arguments)
            self.assertTrue(self.provider.request_received.wait(5))
            repeated = self.adapter().call('causalrun_write', arguments)['structuredContent']
            checked = adapter.call('causalrun_verify', {'action_id': repeated['id']})['structuredContent']
            self.assertEqual(checked['state'], 'IN_DOUBT')
            with storage.connect(self.provider.db_path) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM requests').fetchone()[0], 0)
            self.provider.allow_commit.set()
            completed = pending.result(5)['structuredContent']
        self.assertEqual(completed['state'], 'COMMITTED')
        self.assertEqual(completed['id'], repeated['id'])
        with storage.connect(self.provider.db_path) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM requests').fetchone()[0], 1)
            objects = db.execute('SELECT count(*) FROM values_and_receipts').fetchone()[0]
            self.assertEqual(objects, 1)
        FAULT_RESULTS.append({'fault': 'POST paused before commit, missing GET, release commit', 'uncertain': checked,
                              'recovered': completed, 'provider_posts': 1, 'provider_objects': objects})

    def test_packaged_mcp_prepare_operator_review_and_restart(self):
        state = self.folder / 'installed'; archive = self.folder / 'causalrun.pyz'
        subprocess.run([sys.executable, '-m', 'causalrun.installer', '--build', str(archive)], cwd=test_gate4.ROOT, check=True, capture_output=True)
        subprocess.run([sys.executable, str(archive), '--config-dir', str(self.folder / 'config'), '--state-dir', str(state)], check=True, capture_output=True)
        environment = dict(os.environ, CAUSALRUN_PROVIDER_TOKEN='native-write-token-long', CAUSALRUN_RECEIPT_TOKEN='native-read-token-long')
        client = Client(state, env=environment, archive=archive)
        try:
            review = client.call('causalrun_prepare', dict(self.fields, api_version='1', source=test_gate4.SOURCE,
                                 answers={'expected_behavior': 'Exact value', 'sandbox': 'Yes, only the disposable fixture',
                                          'unknown_policy': 'Keep blocked and request review'}))['structuredContent']
            identifier = review['connector_digest']
            command = [sys.executable, str(archive), '--review', identifier, '--state-dir', str(state)]
            code, output = terminal_approval('', identifier, confirmation='wrong', command=command)
            self.assertNotEqual(code, 0, output)
            code, output = terminal_approval('', identifier, command=command)
            self.assertEqual(code, 0, output)
            self.provider.fault_mode = 'drop_response'
            arguments = dict(self.fields, action_key='stdio-original', payload={'value': 'stdio'})
            original = client.call('causalrun_write', arguments)['structuredContent']
            self.assertEqual(original['state'], 'IN_DOUBT')
            client.close(); client = Client(state, env=environment, archive=archive)
            repeated = client.call('causalrun_write', arguments)['structuredContent']
            self.assertEqual((repeated['id'], repeated['state']), (original['id'], 'IN_DOUBT'))
            confirmed = client.call('causalrun_verify', {'action_id': original['id']})['structuredContent']
            self.assertEqual(confirmed['state'], 'COMMITTED')
            with storage.connect(str(state / 'runtime.sqlite')) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM approvals').fetchone()[0], 1)
            with storage.connect(self.provider.db_path) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM requests').fetchone()[0], 1)
                objects = db.execute('SELECT count(*) FROM values_and_receipts').fetchone()[0]
                self.assertEqual(objects, 1)
            FAULT_RESULTS.append({'fault': 'MCP process restart after lost response', 'uncertain': repeated,
                                  'recovered': confirmed, 'provider_posts': 1, 'provider_objects': objects})
        finally:
            client.close()
            if (state / 'service.json').exists():
                try: os.kill(json.loads((state / 'service.json').read_text())['pid'], signal.SIGTERM)
                except ProcessLookupError: pass
