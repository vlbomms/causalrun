"""Record gate A regressions and a two-shape controlled demonstration."""
import hashlib
import json
import os
import platform
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from causalrun import runtime, storage, validation
from causalrun.contracts import digest
from tests.test_http_json import artifact, provider


def demonstrate():
    server, worker = provider()
    try:
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'TEST_WRITE_TOKEN': 'disposable-write-secret', 'TEST_READ_TOKEN': 'disposable-read-secret'}):
            path = str(Path(directory) / 'runtime.sqlite')
            storage.initialize(path)
            actions = []
            for shape in ('entry', 'record'):
                contract = artifact(server.target, shape)
                identifier = runtime.register(path, contract)
                report = validation.validate(path, identifier)
                assert report['failed'] == 0
                runtime.approve(path, identifier, identifier, digest(report))
                action = runtime.execute(path, identifier, 'demo/' + shape, {'value': 'hello'}, '')
                repeated = runtime.execute(path, identifier, 'demo/' + shape, {'value': 'hello'}, '')
                assert action == repeated and action['state'] == 'COMMITTED'
                assert server.objects[(shape, action['id'])]['value'] == 'hello'
                actions.append({'shape': shape, 'method': contract['adapter']['write']['method'],
                                'validation': report, 'action': action,
                                'repeated_action_id': repeated['id']})
            assert server.writes == 2 and len(server.objects) == 2 and server.reads == 0
            return {'schedule': 'register, fixture validation, explicit test approval, write, repeat for each shape',
                    'approval': 'Test harness invokes operator function; no human or OpenCode approval demonstration',
                    'actions': actions, 'oracle': {'write_requests': server.writes, 'read_requests': server.reads,
                    'objects': len(server.objects), 'stored_values': list(server.objects.values())},
                    'passed': 2, 'failed': 0}
    finally:
        server.shutdown()
        server.server_close()
        worker.join(5)


def main(gate='a'):
    root = Path(__file__).resolve().parents[1]
    output = root / ('docs/results/http-gate-' + gate)
    output.mkdir(parents=True, exist_ok=True)
    names = ['tests.test_gate1', 'tests.test_gate2', 'tests.test_gate3', 'tests.test_gate4',
             'tests.test_gate4_followup', 'tests.test_gate5', 'tests.test_selective_questions',
             'tests.test_usability', 'tests.test_http_json']
    if gate in ('b', 'c', 'd'):
        names.append('tests.test_http_recovery')
    if gate in ('c', 'd'):
        names.append('tests.test_http_harness')
    if gate == 'd':
        names.append('tests.test_http_live_contract')
    with (output / 'tests.txt').open('w') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
    sources = [p for folder in ('causalrun', 'examples', 'adapters', 'tests')
               for p in sorted((root / folder).rglob('*'))
               if p.suffix in ('.py', '.mjs', '.json') and '__pycache__' not in str(p)]
    report = {'command': 'python3 -m tests.run_http_gate_' + gate,
              'recorded_at': datetime.now(timezone.utc).isoformat(),
              'versions': {'python': sys.version, 'sqlite': sqlite3.sqlite_version, 'platform': platform.platform()},
              'tests': result.testsRun, 'passed': result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
              'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
              'source_hashes': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}}
    (output / 'tests.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('tests', 'passed', 'failures', 'errors', 'skipped')}), flush=True)
    if not result.wasSuccessful() or result.skipped:
        return 1
    demonstration = demonstrate()
    (output / 'demonstration.json').write_text(json.dumps(demonstration, indent=2) + '\n')
    if gate in ('b', 'c', 'd'):
        from tests.test_http_recovery import SCHEDULES
        (output / 'schedules.json').write_text(json.dumps(SCHEDULES, indent=2) + '\n')
    if gate in ('c', 'd'):
        from tests.demo_http_opencode import demonstrate_host
        host = demonstrate_host()
        host['command'] = report['command'] + ' (generic host demonstration)'
        (output / 'host.json').write_text(json.dumps(host, indent=2) + '\n')
        print(json.dumps({'host_passed': host['passed'], 'host_failed': host['failed']}), flush=True)
        if host['failed']:
            return 1
    print(json.dumps({'demonstrations_passed': demonstration['passed'], 'oracle': demonstration['oracle']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
