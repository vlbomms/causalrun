"""Skill-only installation, ownership boundaries, packaging, and host discovery."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from causalrun.contracts import Rejected
from causalrun.installer import ROOT, build, install, install_skill


class SkillTests(unittest.TestCase):
    def test_skill_only_preserves_config_runtime_and_other_skills(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            config = folder / 'config'
            config.mkdir()
            settings = '{"permission":{"bash":"deny","causalrun_approve":"ask"}}\n'
            (config / 'opencode.json').write_text(settings)
            other = config / 'skills/other/SKILL.md'
            other.parent.mkdir(parents=True)
            other.write_text('Unrelated user skill')
            result = install_skill(ROOT, config)
            self.assertEqual(Path(result['skill']).read_text(), (ROOT / 'skills/causalrun/SKILL.md').read_text())
            self.assertEqual((config / 'opencode.json').read_text(), settings)
            self.assertEqual(other.read_text(), 'Unrelated user skill')
            self.assertFalse((config / 'plugins').exists())
            self.assertEqual(install_skill(ROOT, config), result)

    def test_collision_blocks_full_install_before_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            config = folder / 'config'
            skill = config / 'skills/causalrun/SKILL.md'
            skill.parent.mkdir(parents=True)
            skill.write_text('User-owned skill')
            settings = '{"username":"keep-me"}'
            (config / 'opencode.json').write_text(settings)
            with self.assertRaises(Rejected):
                install(ROOT, config, folder / 'state')
            self.assertEqual(skill.read_text(), 'User-owned skill')
            self.assertEqual((config / 'opencode.json').read_text(), settings)
            self.assertFalse((folder / 'state').exists())

    def test_zipapp_skill_only_and_full_install(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            archive = folder / 'causalrun.pyz'
            build(archive)
            for mode in ('skill-only', 'full'):
                config = folder / mode
                command = [sys.executable, str(archive), '--config-dir', str(config),
                           '--state-dir', str(folder / ('state-' + mode)), '--json']
                if mode == 'skill-only':
                    command.append('--skill-only')
                run = subprocess.run(command, cwd=folder, capture_output=True, text=True, timeout=30)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertEqual(Path(json.loads(run.stdout)['skill']).read_text(), (ROOT / 'skills/causalrun/SKILL.md').read_text())
                self.assertEqual((config / 'plugins/causalrun.ts').exists(), mode == 'full')

    def test_actual_opencode_global_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            config = folder / 'config/opencode'
            installed = install_skill(ROOT, config)
            environment = dict(os.environ, XDG_CONFIG_HOME=str(folder / 'config'),
                               XDG_DATA_HOME=str(folder / 'data'), XDG_CACHE_HOME=str(folder / 'cache'),
                               XDG_STATE_HOME=str(folder / 'state'), OPENCODE_DISABLE_MODELS_FETCH='true')
            environment.pop('OPENCODE_CONFIG_DIR', None)
            run = subprocess.run([str(ROOT / '.local/opencode-test/node_modules/.bin/opencode'), 'debug', 'skill'],
                                 cwd=folder, env=environment, capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr)
            found = [item for item in json.loads(run.stdout) if item['name'] == 'causalrun']
            self.assertEqual(len(found), 1)
            self.assertEqual(Path(found[0]['location']).resolve(), Path(installed['skill']).resolve())
            self.assertIn('content', found[0])
