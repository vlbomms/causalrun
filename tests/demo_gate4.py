"""Fresh zipapp install and actual pinned OpenCode processes; scripted local model."""
import json
import os
import signal
import select
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from examples.provider import create_server
from tests.opencode_fixture import create_model

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/results/gate-4'
BINARY = ROOT / '.local/opencode-test/node_modules/.bin/opencode'


def http(origin, path, body=None):
    request = Request(origin + path, data=None if body is None else json.dumps(body).encode(),
                      headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=20) as response:
        data = response.read()
        return json.loads(data) if data else None


def demonstration(after_restart=None, model_factory=create_model, global_config=False, new_session_probe=False):
    report = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'command': 'python3 -m tests.demo_gate4',
              'opencode': subprocess.check_output([str(BINARY), '--version'], text=True).strip(),
              'model': 'Scripted local OpenAI-compatible tool-call fixture, no paid/model inference',
              'approval': 'Harness replies to actual OpenCode question and permission HTTP requests; not a human usability test',
              'questions': [], 'permissions': [], 'review_files': [], 'tool_calls': [], 'passed': 0, 'failed': 0}
    with tempfile.TemporaryDirectory() as directory:
        folder = Path(directory)
        state, config, project = folder / 'state', folder / 'config', folder / 'project'
        if global_config:
            config = folder / 'xdg-config' / 'opencode'
        project.mkdir(); config.mkdir(parents=True)
        # Demonstrate preserving an existing unrelated preference.
        (config / 'opencode.json').write_text(json.dumps({'username': 'acceptance-user'}))
        archive = folder / 'causalrun.pyz'
        subprocess.run([sys.executable, '-m', 'causalrun.installer', '--build', str(archive)], cwd=ROOT, check=True, capture_output=True)
        install = subprocess.run([sys.executable, str(archive), '--config-dir', str(config), '--state-dir', str(state), '--json'],
                                 cwd=project, check=True, capture_output=True, text=True)
        report['installation'] = json.loads(install.stdout)
        settings = json.loads((config / 'opencode.json').read_text())
        assert settings['username'] == 'acceptance-user'
        provider = create_server(str(folder / 'provider.sqlite'), 0, 'gate4-provider-write-token', receipt_token='gate4-provider-read-token')
        provider.fault_mode = 'drop_response'
        provider_thread = threading.Thread(target=provider.serve_forever, daemon=True); provider_thread.start()
        target = 'http://127.0.0.1:' + str(provider.server_port)
        model = model_factory(target)
        workflow_started = time.monotonic()
        model_thread = threading.Thread(target=model.serve_forever, daemon=True); model_thread.start()
        settings.update({'model': 'fixture/scripted', 'enabled_providers': ['fixture'], 'share': 'disabled',
                         'provider': {'fixture': {'npm': '@ai-sdk/openai-compatible', 'name': 'Scripted fixture',
                           'options': {'baseURL': 'http://127.0.0.1:' + str(model.server_port) + '/v1', 'apiKey': 'fixture-only'},
                           'models': {'scripted': {'name': 'Scripted fixture', 'limit': {'context': 128000, 'output': 8000}}}}}})
        (config / 'opencode.json').write_text(json.dumps(settings))
        # A direct structured API tool whose execution must be intercepted before its POST.
        (config / 'plugins/direct-test.ts').write_text('''import { tool } from "@opencode-ai/plugin";
export default async () => ({tool:{http_request:tool({description:"Test direct write",args:{method:tool.schema.string(),url:tool.schema.string()},async execute(args){await fetch(args.url,{method:args.method,headers:{Authorization:"Bearer gate4-provider-write-token","Content-Type":"application/json"},body:JSON.stringify({action_id:"bypass",payload:{value:"unsafe"}})});return "sent";}})}});''')
        env = dict(os.environ, OPENCODE_CONFIG_DIR=str(config), XDG_CONFIG_HOME=str(folder / 'xdg-config'),
                   XDG_DATA_HOME=str(folder / 'xdg-data'), XDG_CACHE_HOME=str(folder / 'xdg-cache'),
                   XDG_STATE_HOME=str(folder / 'xdg-state'), OPENCODE_DISABLE_MODELS_FETCH='true',
                   CAUSALRUN_PROVIDER_TOKEN='gate4-provider-write-token', CAUSALRUN_RECEIPT_TOKEN='gate4-provider-read-token')
        if global_config:
            env.pop('OPENCODE_CONFIG_DIR', None)
        processes = []
        log = (folder / 'opencode.log').open('w+')
        service_pid = None
        try:
            def start_host():
                process = subprocess.Popen([str(BINARY), 'serve', '--hostname', '127.0.0.1', '--port', '0', '--print-logs'],
                                           cwd=project, env=env, stdout=subprocess.PIPE, stderr=log, text=True)
                processes.append(process)
                import re
                deadline = time.monotonic() + 30
                lines = []
                while time.monotonic() < deadline:
                    if select.select([process.stdout], [], [], 0.2)[0]:
                        line = process.stdout.readline(); lines.append(line)
                        match = re.search(r'http://127.0.0.1:\d+', line)
                        if match:
                            return process, match.group()
                        if not line:
                            break
                raise AssertionError('OpenCode did not start: ' + ''.join(lines))
            host, origin = start_host()
            session = http(origin, '/session', {})
            session_id = session['id']
            report['session_id'] = session_id

            def run_prompt(text):
                previous_ids = {item['info']['id'] for item in http(origin, '/session/' + session_id + '/message')}
                http(origin, '/session/' + session_id + '/prompt_async', {'parts': [{'type': 'text', 'text': text}]})
                deadline = time.monotonic() + 90
                answered = set()
                while time.monotonic() < deadline:
                    for question in http(origin, '/question'):
                        if question['id'] in answered: continue
                        report['questions'].append(question)
                        http(origin, '/question/' + question['id'] + '/reply', {
                            'answers': [[item['options'][0]['label']] for item in question['questions']]})
                        answered.add(question['id'])
                    for permission in http(origin, '/permission'):
                        if permission['id'] in answered: continue
                        report['permissions'].append(permission)
                        review_file = permission.get('metadata', {}).get('review_file')
                        if review_file:
                            review = json.loads(Path(review_file).read_text())
                            assert review['connector_digest'] == permission['metadata']['connector_digest']
                            assert review['report_digest'] == permission['metadata']['report_digest']
                            report['review_files'].append(review)
                        http(origin, '/permission/' + permission['id'] + '/reply', {'reply': 'once'})
                        answered.add(permission['id'])
                    status = http(origin, '/session/status')
                    if session_id not in status or status[session_id]['type'] == 'idle':
                        messages = http(origin, '/session/' + session_id + '/message')
                        if any(item['info']['id'] not in previous_ids and item['info'].get('role') == 'assistant' and item['info'].get('finish') == 'stop' for item in messages):
                            return messages
                    time.sleep(0.2)
                raise AssertionError('OpenCode prompt did not finish within 90 seconds')

            messages = run_prompt('Run the controlled API acceptance workflow. Never send a direct unapproved write.')
            report['first_session_messages'] = messages
            tools = [part for message in messages for part in message.get('parts', []) if part.get('type') == 'tool']
            assert tools[0]['tool'] == 'http_request' and tools[0]['state']['status'] == 'error'
            writes = [json.loads(part['state']['output']) for part in tools if part['tool'] == 'causalrun_write']
            assert writes[0]['status'] == 'PREPARATION_REQUIRED'
            assert writes[1]['state'] == 'IN_DOUBT' and writes[2]['state'] == 'COMMITTED'
            assert writes[1]['id'] == writes[2]['id']
            report['timeline'] = [{'step': 'first write held', 'state': writes[0]['status']},
                                  {'step': 'provider commit, response lost', 'state': writes[1]['state'], 'action_id': writes[1]['id']},
                                  {'step': 'read recovery and repeated key', 'state': writes[2]['state'], 'action_id': writes[2]['id']}]
            service = json.loads((state / 'service.json').read_text()); service_pid = service['pid']
            with sqlite3.connect(folder / 'provider.sqlite') as db:
                counts = {'objects': db.execute('SELECT count(*) FROM values_and_receipts').fetchone()[0],
                          'writes': db.execute('SELECT count(*) FROM requests').fetchone()[0]}
            report['first_counts'] = counts
            assert counts == {'objects': 1, 'writes': 1}, counts
            assert len(report['questions']) == 1 and len(report['permissions']) == 1
            with sqlite3.connect(state / 'runtime.sqlite') as db:
                action = db.execute('SELECT id,state,receipt FROM actions').fetchone()
                approvals = db.execute('SELECT count(*) FROM approvals').fetchone()[0]
            assert action and action[1] == 'COMMITTED' and approvals == 1
            report['first_action'] = {'id': action[0], 'state': action[1], 'receipt': json.loads(action[2])}
            report['passed'] += 1
            host.kill(); host.wait(10)
            os.kill(service_pid, signal.SIGKILL); service_pid = None
            report['restart_schedule'] = {'host_signal': 'SIGKILL', 'runtime_signal': 'SIGKILL', 'before': service}
            _, origin = start_host()
            # Same persisted OpenCode session, runtime records, approvals, and stable action key.
            restart_messages = run_prompt('Continue after the restart. Reuse the original action key and retrieve the durable result.')
            report['restart_messages'] = restart_messages
            service = json.loads((state / 'service.json').read_text()); service_pid = service['pid']
            report['restart_schedule']['after'] = service
            assert service['instance'] != report['restart_schedule']['before']['instance']
            with sqlite3.connect(folder / 'provider.sqlite') as db:
                final = {'objects': db.execute('SELECT count(*) FROM values_and_receipts').fetchone()[0],
                         'writes': db.execute('SELECT count(*) FROM requests').fetchone()[0]}
            report['final_counts'] = final
            assert final == counts
            assert len(report['permissions']) == 1
            with sqlite3.connect(state / 'runtime.sqlite') as db:
                assert db.execute('SELECT id,state FROM actions').fetchall() == [(action[0], 'COMMITTED')]
            report['timeline'].append({'step': 'host and service restart, same key', 'state': 'COMMITTED', 'action_id': action[0]})
            report['passed'] += 1
            if new_session_probe:
                os.kill(service_pid, signal.SIGKILL); service_pid = None
                new_session = http(origin, '/session', {})
                from causalrun.native import running
                deadline = time.monotonic() + 20
                restarted = None
                while time.monotonic() < deadline:
                    restarted = running(state)
                    if restarted and restarted['instance'] != service['instance']:
                        break
                    time.sleep(0.1)
                assert restarted and restarted['instance'] != service['instance'], 'New session did not start the local service'
                service_pid = restarted['pid']
                report['new_session_startup'] = {'session_id': new_session['id'], 'started_without_tool_call': True,
                                                'instance': restarted['instance'], 'pid': service_pid}
                with sqlite3.connect(folder / 'provider.sqlite') as db:
                    assert db.execute('SELECT count(*) FROM requests').fetchone()[0] == 1
                report['passed'] += 1
            report['workflow_elapsed_seconds'] = time.monotonic() - workflow_started
            if after_restart is not None:
                report['second_harness'] = after_restart(folder, state, target, action, env)
                report['passed'] += 1
        except Exception as error:
            report['failed'] += 1
            report['failure_type'] = type(error).__name__
            report['failure_message'] = str(error)
            import traceback
            report['traceback'] = traceback.format_exc()
            log.flush(); log.seek(0); report['opencode_log'] = log.read()[-12000:]
        finally:
            for process in processes:
                if process.poll() is None: process.kill()
                process.wait(10)
            if service_pid is None and (state / 'service.json').exists():
                service_pid = json.loads((state / 'service.json').read_text())['pid']
            if service_pid:
                try: os.kill(service_pid, signal.SIGTERM)
                except ProcessLookupError: pass
            provider.shutdown(); provider.server_close(); provider_thread.join(5)
            model.shutdown(); model.server_close(); model_thread.join(5)
            log.close()
            report['tool_calls'] = model.calls
    return report


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = demonstration()
    (OUTPUT / 'demonstration.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('passed', 'failed', 'tool_calls')}))
    return 0 if report['failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
