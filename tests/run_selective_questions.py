"""Regressions plus actual OpenCode clear/ambiguous first-use workflows."""
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
    output = root / 'docs/results/selective-questions'; output.mkdir(parents=True, exist_ok=True)
    names = ['tests.test_gate1', 'tests.test_gate2', 'tests.test_gate3', 'tests.test_gate4',
             'tests.test_gate4_followup', 'tests.test_gate5', 'tests.test_selective_questions']
    with (output / 'tests.txt').open('w') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
    sources = [p for folder in ('causalrun', 'examples', 'adapters', 'tests') for p in sorted((root / folder).rglob('*'))
               if p.suffix in ('.py', '.mjs', '.json') and '__pycache__' not in str(p)]
    report = {'command': 'python3 -m tests.run_selective_questions', 'recorded_at': datetime.now(timezone.utc).isoformat(),
              'versions': {'python': sys.version, 'sqlite': sqlite3.sqlite_version, 'platform': platform.platform()},
              'tests': result.testsRun, 'passed': result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
              'failed': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
              'source_hashes': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    (output / 'tests.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('tests', 'passed', 'failed', 'errors', 'skipped')}), flush=True)
    if not result.wasSuccessful(): return 1
    demonstrations = []
    for ambiguous in (False, True):
        demo = demonstration(model_factory=lambda target: create_model(target, selective=True, ambiguous=ambiguous))
        demo['scenario'] = 'ambiguous' if ambiguous else 'documented success'
        labels = [question['header'] for batch in demo['questions'] for question in batch['questions']]
        demo['question_headers'] = labels
        if (not ambiguous and 'Result' in labels) or (ambiguous and labels.count('Result') != 1):
            demo['failed'] += 1; demo['failure_message'] = 'Unexpected success-question count'
        demonstrations.append(demo)
        (output / 'demonstrations.json').write_text(json.dumps(demonstrations, indent=2) + '\n')
        print(json.dumps({'scenario': demo['scenario'], 'questions': labels, 'passed': demo['passed'], 'failed': demo['failed']}), flush=True)
    return 0 if all(demo['failed'] == 0 for demo in demonstrations) else 1


if __name__ == '__main__':
    raise SystemExit(main())
