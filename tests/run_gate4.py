"""Record gate 1–4 regressions plus real OpenCode acceptance with a scripted model."""
import hashlib
import json
import platform
import sqlite3
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tests.demo_gate4 import demonstration


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / 'docs/results/gate-4'; output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    suite = unittest.defaultTestLoader.loadTestsFromNames(['tests.test_gate1', 'tests.test_gate2', 'tests.test_gate3', 'tests.test_gate4', 'tests.test_gate4_followup'])
    with (output / 'tests.txt').open('w') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    sources = [p for folder in ('causalrun', 'examples', 'tests', 'adapters')
               for p in sorted((root / folder).rglob('*')) if p.suffix in ('.py', '.mjs', '.json') and '__pycache__' not in str(p)]
    report = {'command': 'python3 -m tests.run_gate4', 'recorded_at': datetime.now(timezone.utc).isoformat(),
              'versions': {'python': sys.version, 'sqlite': sqlite3.sqlite_version, 'platform': platform.platform()},
              'tests': result.testsRun, 'passed': result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
              'failed': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
              'elapsed_seconds': time.monotonic() - started,
              'source_hashes': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    (output / 'tests.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('tests', 'passed', 'failed', 'errors', 'skipped')}), flush=True)
    if not result.wasSuccessful() or result.skipped: return 1
    demo = demonstration()
    (output / 'demonstration.json').write_text(json.dumps(demo, indent=2) + '\n')
    print(json.dumps({'demonstrations_passed': demo['passed'], 'failed': demo['failed']}))
    return 0 if demo['failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
