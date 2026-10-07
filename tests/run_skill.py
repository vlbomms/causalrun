"""Record skill packaging, discovery, and actual host loading with ordinary input."""
import hashlib
import json
import platform
import sqlite3
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tests.demo_gate4 import demonstration
from tests.opencode_fixture import create_model


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / 'docs/results/skill'
    output.mkdir(parents=True, exist_ok=True)
    names = ['tests.test_gate1', 'tests.test_gate2', 'tests.test_gate3', 'tests.test_gate4',
             'tests.test_gate4_followup', 'tests.test_gate5', 'tests.test_selective_questions',
             'tests.test_usability', 'tests.test_http_json', 'tests.test_http_recovery',
             'tests.test_http_harness', 'tests.test_http_live_contract', 'tests.test_skill']
    with (output / 'tests.txt').open('w') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
    sources = [p for folder in ('causalrun', 'examples', 'adapters', 'tests', 'skills')
               for p in sorted((root / folder).rglob('*'))
               if p.suffix in ('.py', '.mjs', '.json', '.md') and '__pycache__' not in str(p)]
    report = {'command': 'python3 -m tests.run_skill', 'recorded_at': datetime.now(timezone.utc).isoformat(),
              'versions': {'python': sys.version, 'sqlite': sqlite3.sqlite_version, 'platform': platform.platform()},
              'tests': result.testsRun, 'passed': result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
              'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
              'source_hashes': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    (output / 'tests.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('tests', 'passed', 'failures', 'errors', 'skipped')}), flush=True)
    if not result.wasSuccessful() or result.skipped:
        return 1
    host = demonstration(model_factory=lambda target: create_model(target, generic=True, load_skill=True),
                         generic=True, load_skill=True, global_config=True, new_session_probe=True)
    host['command'] = report['command'] + ' (ordinary request and skill loading)'
    (output / 'host.json').write_text(json.dumps(host, indent=2) + '\n')
    print(json.dumps({'host_passed': host['passed'], 'host_failed': host['failed']}), flush=True)
    return 0 if host['failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
