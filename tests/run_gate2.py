"""Record gate 1 regression, gate 2 checks, and separate-process demonstrations."""
import hashlib
import json
import platform
import sqlite3
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tests.demo_gate2 import demonstration

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/results/gate-2'


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    suite = unittest.defaultTestLoader.loadTestsFromNames(['tests.test_gate1', 'tests.test_gate2'])
    with (OUTPUT / 'tests.txt').open('w') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    report = {'command': 'python3 -m tests.run_gate2', 'recorded_at': datetime.now(timezone.utc).isoformat(),
              'versions': {'python': sys.version, 'sqlite': sqlite3.sqlite_version, 'platform': platform.platform()},
              'tests': result.testsRun, 'passed': result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
              'failed': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
              'elapsed_seconds': time.monotonic() - started,
              'source_hashes': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                for folder in ('causalrun', 'examples', 'tests')
                                for path in sorted((ROOT / folder).glob('*'))
                                if path.suffix in ('.py', '.json')}}
    from tests.test_gate2 import OBSERVED_SCHEDULES, REJECTED_VERIFIERS
    (OUTPUT / 'fault-schedules.json').write_text(json.dumps(OBSERVED_SCHEDULES, indent=2) + '\n')
    (OUTPUT / 'rejected-verifiers.json').write_text(json.dumps(REJECTED_VERIFIERS, indent=2) + '\n')
    (OUTPUT / 'tests.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('tests', 'passed', 'failed', 'errors', 'skipped')}), flush=True)
    if not result.wasSuccessful() or result.skipped:
        return 1
    try:
        demo = demonstration()
    except Exception as error:
        (OUTPUT / 'demonstration-failure.txt').write_text(type(error).__name__ + ': ' + str(error) + '\n')
        raise
    (OUTPUT / 'demonstration.json').write_text(json.dumps(demo, indent=2) + '\n')
    print(json.dumps({'demonstrations_passed': demo['passed'], 'failed': demo['failed']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
