"""Record test outcomes, schedules, source hashes, versions, and demo timelines."""
import hashlib
import json
import platform
import sqlite3
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tests.demo_gate1 import demonstration

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/results/gate-1'


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    suite = unittest.defaultTestLoader.loadTestsFromName('tests.test_gate1')
    with (OUTPUT / 'tests.txt').open('w') as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    report = {'command': 'python3 -m tests.run_gate1',
              'recorded_at': datetime.now(timezone.utc).isoformat(),
              'versions': {'python': sys.version, 'sqlite': sqlite3.sqlite_version,
                           'platform': platform.platform()},
              'tests': result.testsRun, 'passed': result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
              'failed': len(result.failures), 'errors': len(result.errors),
              'skipped': len(result.skipped), 'elapsed_seconds': time.monotonic() - started,
              'source_hashes': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                for folder in ('causalrun', 'examples', 'tests')
                                for path in sorted((ROOT / folder).glob('*.py'))}}
    (OUTPUT / 'tests.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('tests', 'passed', 'failed', 'errors', 'skipped')}), flush=True)
    if not result.wasSuccessful() or result.skipped:
        return 1
    demo = demonstration()
    (OUTPUT / 'demonstration.json').write_text(json.dumps(demo, indent=2) + '\n')
    print(json.dumps({'demonstration_passed': demo['passed'], 'failed': demo['failed'],
                      'provider_counts': demo['provider_counts']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
