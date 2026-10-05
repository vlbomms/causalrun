"""Default installation, compact displays, and full review preservation."""
import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from causalrun import storage
from tests import test_gate4


class InstallationTests(unittest.TestCase):
    def test_one_command_uses_global_xdg_config_without_session_flags(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); config = folder / 'config/opencode'; config.mkdir(parents=True)
            (config / 'opencode.json').write_text('{"username":"keep-existing-setting"}')
            environment = dict(os.environ, XDG_CONFIG_HOME=str(folder / 'config'))
            environment.pop('OPENCODE_CONFIG_DIR', None)
            command = [sys.executable, str(test_gate4.ROOT / 'install.py'), '--state-dir', str(folder / 'state')]
            run = subprocess.run(command, env=environment, cwd=folder, capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(len(run.stdout.splitlines()), 3)
            self.assertNotIn('connector_digest', run.stdout)
            self.assertTrue((config / 'plugins/causalrun.ts').exists())
            self.assertEqual(json.loads((config / 'opencode.json').read_text())['username'], 'keep-existing-setting')
            self.assertTrue((config / 'opencode.json.before-causalrun').exists())
            self.assertFalse((folder / 'state/service.json').exists())

    def test_custom_config_override_and_json_output(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            environment = dict(os.environ, OPENCODE_CONFIG_DIR=str(folder / 'custom-config'))
            run = subprocess.run([sys.executable, str(test_gate4.ROOT / 'install.py'), '--state-dir', str(folder / 'state'), '--json'],
                                 env=environment, capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(Path(json.loads(run.stdout)['installed']), (folder / 'custom-config/plugins/causalrun.ts').resolve())


class DisplayTests(unittest.TestCase):
    setUp = test_gate4.NativeTests.setUp
    tearDown = test_gate4.NativeTests.tearDown

    def test_short_results_keep_full_review_and_recovery(self):
        state = self.folder / 'display-state'
        self.provider.fault_mode = 'drop_response'
        environment = dict(os.environ, CAUSALRUN_PROVIDER_TOKEN='native-write-token-long', CAUSALRUN_RECEIPT_TOKEN='native-read-token-long')
        try:
            run = subprocess.run(['node', str(test_gate4.ROOT / 'tests/plugin_display.mjs'), str(test_gate4.ROOT), str(state),
                                  sys.executable, self.target], env=environment, cwd=test_gate4.ROOT, capture_output=True, text=True, timeout=45)
            self.assertEqual(run.returncode, 0, run.stderr)
            result = json.loads(run.stdout)
            self.assertEqual(result['passed'], 7)
            self.assertLess(result['compact_bytes'], result['full_bytes'])
            with storage.connect(self.provider.db_path) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM requests').fetchone()[0], 1)
                self.assertEqual(db.execute('SELECT count(*) FROM values_and_receipts').fetchone()[0], 1)
        finally:
            if (state / 'service.json').exists():
                try: os.kill(json.loads((state / 'service.json').read_text())['pid'], signal.SIGTERM)
                except ProcessLookupError: pass
