"""Authorized sandbox only: two real GitHub POSTs, read recovery, and cleanup.

The response-loss fault is injected after HTTPS returns a real provider receipt.
The PTY approval is scripted test input, not proof of a human security boundary.
Credentials remain in process memory and are never included in evidence.
"""
import argparse
import json
import secrets
import subprocess
import tempfile
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from causalrun import github, runtime, storage, validation
from causalrun.contracts import digest
from causalrun.server import create_server
from causalrun.transport import request, request_with_headers
from tests.test_gate1 import terminal_approval
from tests.test_gate3 import artifact

REPOSITORY = 'vlbomms/causalrun-connector-tests'
ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/results/gate-3/live-demonstration.json'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    args = parser.parse_args()
    if args.repository != REPOSITORY:
        raise SystemExit('This demonstration is authorized only for ' + REPOSITORY)
    token = subprocess.check_output(['gh', 'auth', 'token', '--hostname', 'github.com'], text=True).strip()
    author = subprocess.check_output(['gh', 'api', 'user', '--jq', '.login'], text=True).strip()
    report = {'command': 'python3 -m tests.demo_gate3_live --repository ' + REPOSITORY,
              'recorded_at': datetime.now(timezone.utc).isoformat(), 'repository': REPOSITORY,
              'author': author, 'api_version': github.VERSION,
              'approval': 'Scripted PTY test approval; user authorized this disposable repository in chat',
              'response_loss': 'Harness discards the real HTTPS response after provider creation; not a network outage',
              'credential_scope': 'Local gh credential reused for read-only recovery; it has write privileges',
              'schedules': [], 'created_issues': [], 'cleanup': [], 'passed': 0, 'failed': 0}
    real_request = github.request_with_headers
    created = []
    server = worker = None
    try:
        with tempfile.TemporaryDirectory() as directory:
            db = str(Path(directory) / 'runtime.sqlite')
            storage.initialize(db)
            contract = artifact(repository=REPOSITORY, author=author)
            identifier = runtime.register(db, contract)
            validated = validation.validate(db, identifier)
            report['connector_digest'] = identifier
            report['validation'] = validated
            report['artifact'] = contract
            assert validated['failed'] == 0 and validated['passed'] == 11
            code, _ = terminal_approval(db, identifier)
            assert code == 0
            agent_token = secrets.token_hex(24)
            server = create_server(db, 0, agent_token, token)
            worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
            target = 'http://127.0.0.1:' + str(server.server_port)
            run_id = secrets.token_hex(5)

            def provider_call(target, path, credential, body=None, **kwargs):
                response = real_request(target, path, credential, body, **kwargs)
                if body is not None and kwargs.get('method') is None:
                    # Keep the provider oracle before deliberately dropping the receipt.
                    issue = response[1]
                    created.append(issue)
                    if 'lost-response' in body['title']:
                        raise TimeoutError('Injected response loss after provider creation')
                return response

            with patch('causalrun.github.request_with_headers', side_effect=provider_call):
                for phase in ('normal', 'lost-response'):
                    payload = {'title': '[causalrun sandbox ' + run_id + '] ' + phase,
                               'body': 'Authorized gate 3 connector acceptance test. This issue will be closed after the run.'}
                    body = {'connector_digest': identifier, 'action_key': run_id + '-' + phase, 'payload': payload}
                    _, action = request(target, '/v1/actions', agent_token, body)
                    expected_state = 'COMMITTED' if phase == 'normal' else 'IN_DOUBT'
                    assert action['state'] == expected_state, action
                    timeline = {'phase': phase, 'initial': action, 'steps': []}
                    report['schedules'].append(timeline)
                    issue = created[-1]
                    issue_path = '/repos/' + REPOSITORY + '/issues/' + str(issue['number'])
                    _, oracle, _ = request_with_headers('https://api.github.com', issue_path, token, headers=github.HEADERS)
                    assert oracle['title'] == payload['title'] and oracle['body'] == issue['body']
                    timeline['oracle'] = {k: oracle[k] for k in ('id', 'number', 'html_url', 'title', 'body', 'state')}
                    if phase == 'lost-response':
                        # A real edit removes recovery evidence; absence must not authorize another POST.
                        request_with_headers('https://api.github.com', issue_path, token,
                                             {'body': payload['body']}, method='PATCH', headers=github.HEADERS)
                        _, uncertain = request(target, '/v1/actions/' + action['id'] + '/verify', agent_token, {})
                        assert uncertain['state'] == 'IN_DOUBT'
                        timeline['steps'].append({'fault': 'Real marker removal', 'result': uncertain})
                        _, repeated = request(target, '/v1/actions', agent_token, body)
                        assert repeated['id'] == action['id'] and len(created) == 2
                        timeline['steps'].append({'fault': 'Repeat while uncertain', 'result': repeated, 'creation_posts': len(created)})
                        request_with_headers('https://api.github.com', issue_path, token,
                                             {'body': issue['body']}, method='PATCH', headers=github.HEADERS)
                    for check in range(20):
                        _, recovered = request(target, '/v1/actions/' + action['id'] + '/verify', agent_token, {})
                        timeline['steps'].append({'fault': 'Recovery read after restore', 'check': check + 1,
                                                  'state': recovered['state']})
                        if recovered['state'] == 'COMMITTED':
                            break
                        time.sleep(1)
                    assert recovered['state'] == 'COMMITTED'
                    timeline['final'] = recovered
                    with patch('causalrun.github.lookup', side_effect=AssertionError('Durable result must avoid provider read')):
                        _, durable = request(target, '/v1/actions/' + action['id'] + '/verify', agent_token, {})
                    assert durable == recovered
                    report['passed'] += 1
            report['creation_posts'] = len(created)
            assert len(created) == 2
    except Exception as error:
        report['failed'] += 1
        # Provider exceptions can contain request details; record type only.
        report['failure_type'] = type(error).__name__
        report['failure_location'] = [{'file': Path(frame.filename).name, 'line': frame.lineno}
                                      for frame in traceback.extract_tb(error.__traceback__)]
    finally:
        if server is not None:
            server.shutdown(); server.server_close(); worker.join(5)
        for issue in created:
            report['created_issues'].append({'number': issue['number'], 'url': issue['html_url']})
            try:
                issue_path = '/repos/' + REPOSITORY + '/issues/' + str(issue['number'])
                request_with_headers('https://api.github.com', issue_path, token,
                                     {'state': 'closed'}, method='PATCH', headers=github.HEADERS)
                _, found, _ = request_with_headers('https://api.github.com', issue_path, token, headers=github.HEADERS)
                assert found['state'] == 'closed'
                report['cleanup'].append({'number': issue['number'], 'state': found['state'], 'passed': True})
            except Exception as error:
                report['cleanup'].append({'number': issue['number'], 'passed': False, 'error_type': type(error).__name__})
                report['failed'] += 1
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'passed': report['passed'], 'failed': report['failed'],
                          'created': len(created), 'cleanup': report['cleanup']}))
    return 0 if report['failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
