import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from causalrun import native, storage
from causalrun.contracts import Rejected, digest
from causalrun.installer import install
from causalrun.server import create_server
from causalrun.transport import request
from examples.provider import create_server as create_provider

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'examples/verify_value.py').read_text()


class InstallationTests(unittest.TestCase):
    def test_preserve_settings_and_refuse_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); config = folder / 'config'; config.mkdir()
            path = config / 'opencode.json'; path.write_text(json.dumps({'model': 'existing/model', 'permission': {'bash': 'ask'}}))
            install(ROOT, config, folder / 'state')
            value = json.loads(path.read_text())
            self.assertEqual(value['model'], 'existing/model')
            self.assertEqual(value['permission'], {'bash': 'ask', 'causalrun_approve': 'ask'})
            backup = (config / 'opencode.json.before-causalrun').read_text()
            install(ROOT, config, folder / 'state')
            self.assertEqual((config / 'opencode.json.before-causalrun').read_text(), backup)
            (config / 'plugins/causalrun.ts').write_text('unrelated plugin')
            with self.assertRaises(Rejected): install(ROOT, config, folder / 'state')

    def test_jsonc_and_permission_shorthand_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); config = folder / 'config'; config.mkdir()
            path = config / 'opencode.jsonc'; path.write_text('{ // keep comment\n}')
            with self.assertRaises(Rejected): install(ROOT, config, folder / 'state')
            self.assertEqual(path.read_text(), '{ // keep comment\n}')
            path.unlink(); path = config / 'opencode.json'; path.write_text('{"permission":"deny"}')
            with self.assertRaises(Rejected): install(ROOT, config, folder / 'state')
            self.assertEqual(path.read_text(), '{"permission":"deny"}')


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.folder = Path(self.temp.name)
        self.db = str(self.folder / 'runtime.sqlite'); storage.initialize(self.db)
        with storage.connect(self.db) as db: db.execute(native.BINDINGS)
        self.provider = create_provider(str(self.folder / 'provider.sqlite'), 0, 'native-write-token-long', receipt_token='native-read-token-long')
        self.provider_thread = threading.Thread(target=self.provider.serve_forever, daemon=True); self.provider_thread.start()
        self.target = 'http://127.0.0.1:' + str(self.provider.server_port)
        self.fields = {'operation': 'controlled.value.create.v1', 'target': self.target}
        self.server = create_server(self.db, 0, 'native-agent-token-long', 'native-write-token-long', 'native-read-token-long')
        self.server.RequestHandlerClass = native.NativeHandler
        self.server.operator_token = 'native-operator-token-long'; self.server.instance = 'test-instance'; self.server.github_author = None; self.server.credential_operation = 'controlled.value.create.v1'
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True); self.worker.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        for server, worker in ((self.server, self.worker), (self.provider, self.provider_thread)):
            server.shutdown(); server.server_close(); worker.join(5)
        self.temp.cleanup()

    def prepare(self, source=SOURCE):
        return native.prepare(self.db, dict(self.fields, source=source, api_version='1', answers={
            'expected_behavior': 'Exact value', 'sandbox': 'Yes, only the disposable fixture',
            'unknown_policy': 'Keep blocked and request review'}), None)

    def test_first_use_preparation_does_not_send_and_agent_cannot_approve(self):
        self.assertFalse(native.binding(self.db, self.fields)['ready'])
        review = self.prepare()
        self.assertEqual(review['validation']['failed'], 0)
        self.assertFalse(native.binding(self.db, self.fields)['ready'])
        with self.assertRaises(HTTPError) as error:
            request(self.url, '/native/approve', 'native-agent-token-long', {
                'connector_digest': review['connector_digest'], 'report_digest': review['report_digest'], 'scope': self.fields})
        self.assertEqual(error.exception.code, 401)
        with storage.connect(self.provider.db_path) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM requests').fetchone()[0], 0)

    def test_exact_review_and_scope_required_then_reuse(self):
        review = self.prepare()
        body = {'connector_digest': review['connector_digest'], 'report_digest': review['report_digest'], 'scope': self.fields}
        for override in ({'report_digest': 'changed'}, {'scope': dict(self.fields, target='http://127.0.0.1:1')}):
            with self.assertRaises(HTTPError): request(self.url, '/native/approve', self.server.operator_token, dict(body, **override))
        _, approved = request(self.url, '/native/approve', self.server.operator_token, body)
        self.assertTrue(approved['ready'])
        self.assertEqual(approved['connector_digest'], review['connector_digest'])
        self.assertFalse(native.binding(self.db, dict(self.fields, target='http://127.0.0.1:1'))['ready'])

    def test_bad_source_cannot_be_approved(self):
        review = self.prepare('def verify(action_id, payload, evidence):\n    return True\n')
        self.assertGreater(review['validation']['failed'], 0)
        with self.assertRaises(HTTPError):
            request(self.url, '/native/approve', self.server.operator_token, {
                'connector_digest': review['connector_digest'], 'report_digest': review['report_digest'], 'scope': self.fields})

    def test_unknown_operation_and_target_override_rejected(self):
        with self.assertRaises(Rejected): native.scope({'operation': 'arbitrary.post'})
        with self.assertRaises(Rejected): native.scope({'operation': 'controlled.value.create.v1', 'target': 'https://example.com'})
        with self.assertRaises(Rejected): native.prepare(self.db, {'operation': 'github.issue.create.v1', 'repository': 'owner/repo', 'source': SOURCE, 'answers': {}}, None)

    def test_provider_credential_profile_blocks_dispatch(self):
        review = self.prepare()
        request(self.url, '/native/approve', self.server.operator_token, {
            'connector_digest': review['connector_digest'], 'report_digest': review['report_digest'], 'scope': self.fields})
        self.server.credential_operation = 'github.issue.create.v1'
        with self.assertRaises(HTTPError) as error:
            request(self.url, '/v1/actions', 'native-agent-token-long', {
                'connector_digest': review['connector_digest'], 'action_key': 'wrong-credential-profile', 'payload': {'value': 'test'}})
        self.assertEqual(error.exception.code, 400)
        with storage.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM actions').fetchone()[0], 0)

    def test_plugin_rejects_auto_approval_and_direct_writes(self):
        state = self.folder / 'plugin-state'
        env = dict(os.environ, CAUSALRUN_PROVIDER_TOKEN='native-write-token-long', CAUSALRUN_RECEIPT_TOKEN='native-read-token-long')
        try:
            run = subprocess.run(['node', str(ROOT / 'tests/plugin_gate4.mjs'), str(ROOT), str(state),
                                  sys.executable, self.target], env=env, cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)['passed'], 4)
            with storage.connect(str(state / 'runtime.sqlite')) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM approvals').fetchone()[0], 0)
                self.assertEqual(db.execute('SELECT count(*) FROM actions').fetchone()[0], 0)
        finally:
            if (state / 'service.json').exists():
                try: os.kill(json.loads((state / 'service.json').read_text())['pid'], signal.SIGTERM)
                except ProcessLookupError: pass
