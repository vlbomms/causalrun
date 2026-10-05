"""Record gate 1–3 regression results without rewriting prior gate evidence."""
import hashlib
import json
import platform
import sqlite3
import sys
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / 'docs/results/gate-3'
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    suite = unittest.defaultTestLoader.loadTestsFromNames(['tests.test_gate1', 'tests.test_gate2', 'tests.test_gate3'])
    with (output / 'tests.txt').open('w') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    report = {'command': 'python3 -m tests.run_gate3', 'recorded_at': datetime.now(timezone.utc).isoformat(),
              'versions': {'python': sys.version, 'sqlite': sqlite3.sqlite_version, 'platform': platform.platform()},
              'tests': result.testsRun, 'passed': result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
              'failed': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
              'elapsed_seconds': time.monotonic() - started,
              'source_hashes': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for folder in ('causalrun', 'examples', 'tests')
                                for p in sorted((root / folder).glob('*.py'))}}
    (output / 'tests.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('tests', 'passed', 'failed', 'errors', 'skipped')}))
    return 0 if result.wasSuccessful() and not result.skipped else 1


if __name__ == '__main__':
    raise SystemExit(main())
