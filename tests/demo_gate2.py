"""Host-agent workflow plus real process exits, response loss, and durable recovery."""
import json
import os
import pty
import secrets
import select
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from causalrun.transport import request
from tests.test_gate1 import terminal_approval

ROOT = Path(__file__).resolve().parents[1]


def terminal_interview(command, answers):
    master, slave = pty.openpty()
    process = subprocess.Popen(command, cwd=ROOT, stdin=slave, stdout=slave, stderr=slave)
    os.close(slave)
    output = b''
    sent = 0
    try:
        deadline = time.monotonic() + 10
        while process.poll() is None:
            if time.monotonic() > deadline:
                raise AssertionError('Interview did not finish')
            if select.select([master], [], [], 0.1)[0]:
                try:
                    output += os.read(master, 65536)
                except OSError:
                    break
            prompts = output.count(b'Choose a number or enter your own answer:')
            if prompts > sent and sent < len(answers):
                os.write(master, (answers[sent] + '\n').encode())
                sent += 1
        assert process.wait(timeout=5) == 0, output.decode()
        assert sent == 3
        return {'questions_answered': sent, 'used_free_text': answers[0] not in ('1', '2')}
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)


def scenario(phase, evaluate=False):
    processes = []
    tokens = {name: secrets.token_hex(24) for name in ('AGENT', 'PROVIDER', 'RECEIPT')}
    env = dict(os.environ, **{'CAUSALRUN_' + name + '_TOKEN': token for name, token in tokens.items()})
    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        runtime_db = str(directory / 'runtime.sqlite')
        provider_db = str(directory / 'provider.sqlite')
        commands = []

        def start(command):
            child = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True)
            processes.append(child)
            line = child.stdout.readline()
            assert line, child.stderr.read()
            return child, 'http://127.0.0.1:' + str(json.loads(line)['listening'][1])

        def operator(*args):
            commands.append(list(args))
            run = subprocess.run([sys.executable, '-m', 'causalrun', '--db', runtime_db, *args],
                                 cwd=ROOT, capture_output=True, text=True)
            assert run.returncode == 0, run.stderr
            return run.stdout

        def counts():
            with sqlite3.connect(provider_db) as db:
                return {'objects': db.execute('SELECT count(*) FROM values_and_receipts').fetchone()[0],
                        'writes': db.execute('SELECT count(*) FROM requests').fetchone()[0]}

        try:
            _, target = start([sys.executable, '-m', 'examples.provider', '--db', provider_db,
                               '--port', '0', '--fault', 'drop_response' if phase == 'lost_response' else 'none'])
            started = time.monotonic()
            # Discovery is stdout-only and discarded; contract inputs survive.
            facts = json.loads(operator('discover', '--spec', target + '/openapi.json'))
            assert facts['authentication']['providerBearer']['scheme'] == 'bearer'
            answers_file = directory / 'interview.json'
            interaction = terminal_interview([
                sys.executable, '-m', 'causalrun', 'interview', '--spec', target + '/openapi.json',
                '--target', target, '--output', str(answers_file)],
                ['1', '1', '1'] if evaluate else ['Exact matching value and the original action identity', '1', '2'])
            commands.append(['interview'])
            source_file = directory / 'agent_verifier.py'
            source_file.write_text((ROOT / 'examples/verify_value.py').read_text())
            artifact_file = directory / 'connector.json'
            negative = None
            if evaluate:
                source_file.write_text('def verify(action_id, payload, evidence):\n    return True\n')
                operator('build', '--interview', str(answers_file), '--verifier', str(source_file), '--output', str(artifact_file))
                bad_id = json.loads(operator('register', str(artifact_file)))['connector_digest']
                commands.append(['validate', bad_id])
                rejected = subprocess.run([sys.executable, '-m', 'causalrun', '--db', runtime_db, 'validate', bad_id], cwd=ROOT, capture_output=True, text=True)
                negative = json.loads(rejected.stdout)
                assert rejected.returncode != 0 and negative['failed'] > 0, negative
                source_file.write_text((ROOT / 'examples/verify_value.py').read_text())
            operator('build', '--interview', str(answers_file), '--verifier', str(source_file),
                     '--output', str(artifact_file))
            artifact = json.loads(artifact_file.read_text())
            identifier = json.loads(operator('register', str(artifact_file)))['connector_digest']
            validation = json.loads(operator('validate', identifier))
            assert (validation['passed'], validation['failed']) == (10, 0)
            status, text = terminal_approval(runtime_db, identifier)
            commands.append(['approve', identifier])
            assert status == 0, text
            source_file.unlink()
            artifact_file.unlink()
            if phase == 'lost_response':
                commands.append(['serve'])
                child, base = start([sys.executable, '-m', 'causalrun', '--db', runtime_db, 'serve', '--port', '0'])
            else:
                child, base = start([sys.executable, '-m', 'tests.crash_runtime', '--db', runtime_db, '--phase', phase])
            body = {'connector_digest': identifier, 'action_key': 'opencode-acceptance-write' if evaluate else 'generated-demo',
                    'payload': {'value': 'OpenCode durable value' if evaluate else 'hello'}}
            client_lost_response = False
            try:
                action = request(base, '/v1/actions', tokens['AGENT'], body)[1]
                assert phase == 'lost_response' and action['state'] == 'IN_DOUBT'
            except Exception:
                client_lost_response = True
                assert phase != 'lost_response'
                assert child.wait(timeout=5) == 71
            with sqlite3.connect(runtime_db) as db:
                before = db.execute('SELECT id,state FROM actions').fetchall()
            before_counts = counts()
            pre_restart_recovery = None
            if evaluate:
                assert action['state'] == 'IN_DOUBT'
                pre_restart_recovery = request(base, '/v1/actions/' + action['id'] + '/verify', tokens['AGENT'], {})[1]
                assert pre_restart_recovery['state'] == 'COMMITTED'
                assert request(base, '/v1/actions', tokens['AGENT'], body)[1]['id'] == action['id']
                assert request(base, '/v1/actions/' + action['id'], tokens['AGENT'])[1] == pre_restart_recovery
                assert counts() == before_counts
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=5)
            _, base = start([sys.executable, '-m', 'causalrun', '--db', runtime_db, 'serve', '--port', '0'])
            commands.append(['serve'])
            replay = request(base, '/v1/actions', tokens['AGENT'], body)[1]
            if before:
                assert replay['id'] == before[0][0]
                assert counts() == before_counts
            checked = request(base, '/v1/actions/' + replay['id'] + '/verify', tokens['AGENT'], {})[1]
            expected_state = 'IN_DOUBT' if phase == 'after_authorization_commit' else 'COMMITTED'
            assert checked['state'] == expected_state
            expected_counts = {'objects': 0, 'writes': 0} if phase == 'after_authorization_commit' else {'objects': 1, 'writes': 1}
            assert counts() == expected_counts
            assert request(base, '/v1/actions/' + checked['id'], tokens['AGENT'])[1] == checked
            assert counts() == expected_counts
            return {'phase': phase, 'passed': True, 'interview': interaction,
                    'workflow_elapsed_seconds': time.monotonic() - started,
                    'operator_commands': commands, 'negative_validation': negative,
                    'pre_restart_recovery': pre_restart_recovery,
                    'contract_answers': artifact['interview'], 'connector_digest': identifier,
                    'verifier_source': artifact['verifier']['source'],
                    'validation': validation, 'client_lost_response': client_lost_response,
                    'before_restart_actions': before, 'before_restart_counts': before_counts,
                    'action': checked, 'provider_counts': counts(),
                    'false_successes': int(checked['state'] == 'COMMITTED' and counts()['objects'] != 1),
                    'false_failures': int(checked['state'] == 'FAILED' and counts()['objects'] > 0),
                    'unsafe_repeats': max(0, counts()['writes'] - 1)}
        finally:
            for child in reversed(processes):
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=5)
                child.stdout.close()
                child.stderr.close()


def demonstration():
    cases = [scenario(phase) for phase in ('lost_response', 'before_authorization_commit',
             'after_authorization_commit', 'after_provider_commit', 'after_receipt_commit')]
    return {'passed': len(cases), 'failed': 0, 'cases': cases,
            'generator': 'Codex host agent wrote examples/verify_value.py after inspecting examples/openapi.json. '
                         'The build command only packages this source; no embedded model or remote model API is used.',
            'interview': 'Real CLI pseudo-terminal; scripted options and free-text answers, not a live OpenCode session.',
            'schedule': 'Provider and runtime are separate processes. Test harness exits runtime with code 71 '
                        'at explicit SQL/provider boundaries. Provider response loss disconnects after actual commit.',
            'scope': 'Controlled receipt API only; actual runtime, SQLite, HTTP, operator CLI, and pinned source.'}


if __name__ == '__main__':
    print(json.dumps(demonstration(), indent=2))
