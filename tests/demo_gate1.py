"""Separate processes: preflight rejects, operator approval, one write, restart/read."""
import copy
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from causalrun.contracts import digest, example_artifact
from causalrun.transport import request
from tests.test_gate1 import terminal_approval

ROOT = Path(__file__).resolve().parents[1]


def demonstration():
    steps = []
    processes = []
    agent_token, provider_token = secrets.token_hex(24), secrets.token_hex(24)
    with tempfile.TemporaryDirectory() as directory:
        runtime_db = str(Path(directory) / 'runtime.sqlite')
        provider_db = str(Path(directory) / 'provider.sqlite')
        env = dict(os.environ, CAUSALRUN_AGENT_TOKEN=agent_token,
                   CAUSALRUN_PROVIDER_TOKEN=provider_token)

        def operator(*args, succeeds=True):
            command = [sys.executable, '-m', 'causalrun', '--db', runtime_db, *args]
            run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            if succeeds:
                assert run.returncode == 0, run.stderr
                return json.loads(run.stdout)
            assert run.returncode == 1
            return run.stderr.strip()

        def start(command):
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            processes.append(process)
            line = process.stdout.readline()
            assert line, process.stderr.read()
            port = json.loads(line)['listening'][1]
            return process, 'http://127.0.0.1:' + str(port)

        def counts():
            with sqlite3.connect(provider_db) as db:
                return {'objects': db.execute('SELECT count(*) FROM values_and_receipts').fetchone()[0],
                        'writes': db.execute('SELECT count(*) FROM requests').fetchone()[0]}

        try:
            _, target = start([sys.executable, '-m', 'examples.provider', '--db', provider_db, '--port', '0'])
            operator('init')
            process, base = start([sys.executable, '-m', 'causalrun', '--db', runtime_db, 'serve', '--port', '0'])
            artifact = example_artifact(target)
            file = Path(directory) / 'connector.json'
            file.write_text(json.dumps(artifact))
            identifier = operator('register', str(file))['connector_digest']

            def send(connector_digest=identifier):
                return request(base, '/v1/actions', agent_token,
                               {'connector_digest': connector_digest, 'action_key': 'demo-write',
                                'payload': {'value': 'hello'}})[1]

            def rejected(name, identifier=identifier, status=409):
                try:
                    send(identifier)
                except HTTPError as error:
                    assert error.code == status
                    steps.append({'step': name, 'status': error.code, 'counts': counts(),
                                  'error': json.load(error)['error']})
                else:
                    raise AssertionError(name + ' permitted a write')
                assert counts() == {'objects': 0, 'writes': 0}

            missing = copy.deepcopy(artifact)
            del missing['verifier']
            file.write_text(json.dumps(missing))
            operator('register', str(file), succeeds=False)
            rejected('missing_verifier', digest(missing), 404)
            rejected('missing_validation')
            validation_report = operator('validate', identifier)
            rejected('missing_approval')
            code, output = terminal_approval(runtime_db, identifier)
            assert code == 0, output
            steps.append({'step': 'interactive_operator_approval', 'connector_digest': identifier})
            for field, value in [('sources', ['modified artifact']), ('target', 'http://127.0.0.1:1')]:
                modified = copy.deepcopy(artifact)
                modified[field] = value
                file.write_text(json.dumps(modified))
                new_id = operator('register', str(file))['connector_digest']
                rejected('changed_' + field, new_id)
            action = send()
            assert action['state'] == 'COMMITTED'
            assert counts() == {'objects': 1, 'writes': 1}
            steps.append({'step': 'approved_write', 'counts': counts(), 'action': action})
            process.terminate()
            process.wait(timeout=5)
            _, base = start([sys.executable, '-m', 'causalrun', '--db', runtime_db, 'serve', '--port', '0'])
            read = request(base, '/v1/actions/' + action['id'], agent_token)[1]
            assert read == action
            assert send() == action
            assert counts() == {'objects': 1, 'writes': 1}
            steps.append({'step': 'process_restart_durable_read_and_repeat', 'counts': counts(), 'action': read})
            return {'passed': 8, 'failed': 0, 'steps': steps, 'validation': validation_report,
                    'schedule': 'Separate provider/runtime processes; preflight rejects; sandbox validation; '
                                'PTY operator approval; changed-artifact rejects; one accepted write; '
                                'runtime SIGTERM/restart; durable GET and repeated POST without provider resend.',
                    'artifact': artifact, 'provider_counts': counts()}
        finally:
            for process in reversed(processes):
                if process.poll() is None:
                    process.terminate()
                process.wait(timeout=5)
                process.stdout.close()
                process.stderr.close()


if __name__ == '__main__':
    print(json.dumps(demonstration(), indent=2))
