"""Record all gate regressions and the declared MCP fault schedules."""
import hashlib
import json
import platform
import sqlite3
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tests import test_gate5


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / 'docs/results/gate-5'; output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    suite = unittest.defaultTestLoader.loadTestsFromNames([
        'tests.test_gate1', 'tests.test_gate2', 'tests.test_gate3', 'tests.test_gate4',
        'tests.test_gate4_followup', 'tests.test_gate5'])
    with (output / 'tests.txt').open('w') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    sources = [p for folder in ('causalrun', 'examples', 'tests', 'adapters') for p in sorted((root / folder).rglob('*'))
               if p.suffix in ('.py', '.mjs', '.json') and '__pycache__' not in str(p)]
    report = {'command': 'python3 -m tests.run_gate5', 'recorded_at': datetime.now(timezone.utc).isoformat(),
              'versions': {'python': sys.version, 'sqlite': sqlite3.sqlite_version, 'platform': platform.platform()},
              'tests': result.testsRun, 'passed': result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
              'failed': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
              'elapsed_seconds': time.monotonic() - started,
              'source_hashes': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    (output / 'tests.json').write_text(json.dumps(report, indent=2) + '\n')
    faults = test_gate5.FAULT_RESULTS
    (output / 'fault-schedules.json').write_text(json.dumps({'schedules': faults,
        'blocked_observations': sum(case['uncertain']['state'] == 'IN_DOUBT' for case in faults),
        'recovered': sum(case['recovered']['state'] == 'COMMITTED' for case in faults),
        'provider_posts': sum(case['provider_posts'] for case in faults),
        'provider_objects': sum(case['provider_objects'] for case in faults)}, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('tests', 'passed', 'failed', 'errors', 'skipped')}))
    return 0 if result.wasSuccessful() and not result.skipped else 1


if __name__ == '__main__':
    raise SystemExit(main())
