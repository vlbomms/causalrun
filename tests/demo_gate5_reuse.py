"""Use one approval, artifact, and action through real OpenCode and Codex CLI."""
import json
import os
import shutil
import sqlite3
import subprocess
import threading
import time
from pathlib import Path
from tests.codex_fixture import create_model
from tests.demo_gate4 import demonstration, ROOT

OUTPUT = ROOT / 'docs/results/gate-5'


def codex_reuse(folder, state, target, action, original_env):
    model = create_model(target, 'opencode-acceptance-write')
    thread = threading.Thread(target=model.serve_forever, daemon=True); thread.start()
    binary = shutil.which('codex')
    if binary is None: raise AssertionError('Codex CLI is required for the second-host demonstration')
    archive = folder / 'causalrun.pyz'
    config = {
        'model_provider': 'causalrun_fixture', 'model': 'scripted-fixture', 'approval_policy': 'never',
        'model_providers.causalrun_fixture.name': 'Local scripted test fixture',
        'model_providers.causalrun_fixture.base_url': 'http://127.0.0.1:' + str(model.server_port) + '/v1',
        'model_providers.causalrun_fixture.env_key': 'CAUSALRUN_TEST_MODEL_TOKEN',
        'model_providers.causalrun_fixture.wire_api': 'responses',
        'model_providers.causalrun_fixture.requires_openai_auth': False,
        'model_providers.causalrun_fixture.supports_websockets': False,
        'model_providers.causalrun_fixture.request_max_retries': 0,
        'model_providers.causalrun_fixture.stream_max_retries': 0,
        'mcp_servers.causalrun.command': os.sys.executable,
        'mcp_servers.causalrun.args': [str(archive), '--mcp', '--state-dir', str(state)],
        'mcp_servers.causalrun.startup_timeout_sec': 20,
        'mcp_servers.causalrun.tool_timeout_sec': 30,
        'mcp_servers.causalrun.required': True,
        'mcp_servers.causalrun.tools.causalrun_write.approval_mode': 'approve',
        'features.apps': False, 'features.plugins': False, 'features.remote_plugin': False,
        'features.shell_tool': False, 'features.shell_snapshot': False,
    }
    # JSON scalar/array syntax is also valid TOML for these configuration values.
    command = [binary, 'exec', '--ignore-user-config', '--ignore-rules', '--ephemeral', '--skip-git-repo-check',
               '--sandbox', 'read-only', '--json', '--cd', str(folder / 'project')]
    for key, value in config.items(): command += ['-c', key + '=' + json.dumps(value)]
    command += ['Use the causalrun MCP tools to repeat the original action key and retrieve its durable result. Do not prepare another connector or send a direct write.']
    env = dict(original_env, CAUSALRUN_TEST_MODEL_TOKEN='local-fixture-only')
    started = time.monotonic()
    try:
        run = subprocess.run(command, env=env, cwd=ROOT, capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        report = {'codex': subprocess.check_output([binary, '--version'], text=True).strip(),
                  'model': 'Local scripted Responses fixture, no model inference', 'config_overrides': config,
                  'elapsed_seconds': time.monotonic() - started, 'returncode': run.returncode,
                  'events': [json.loads(line) for line in run.stdout.splitlines() if line.strip().startswith('{')],
                  'stderr': run.stderr[-12000:], 'model_calls': model.calls, 'advertised_tools': model.advertised_tools,
                  'model_inputs': model.inputs}
        OUTPUT.mkdir(parents=True, exist_ok=True)
        (OUTPUT / 'codex-attempt.json').write_text(json.dumps(report, indent=2) + '\n')
        assert run.returncode == 0, run.stderr[-2000:]
        assert model.failure is None, model.failure
        assert len([call for call in model.calls if call['tool']]) == 3, model.calls
        assert model.action_id == action[0], ('Actual tool response must return the original action', model.action_id)
        completed = [event['item'] for event in report['events'] if event.get('type') == 'item.completed'
                     and event.get('item', {}).get('type') == 'mcp_tool_call']
        assert len(completed) == 3 and all(item.get('status') == 'completed' and not item.get('error') for item in completed), completed
        with sqlite3.connect(state / 'runtime.sqlite') as db:
            rows = db.execute('SELECT id,state,connector_digest FROM actions').fetchall()
            assert len(rows) == 1 and rows[0][:2] == (action[0], 'COMMITTED'), rows
            assert db.execute('SELECT count(*) FROM approvals').fetchone()[0] == 1
        with sqlite3.connect(folder / 'provider.sqlite') as db:
            counts = {'objects': db.execute('SELECT count(*) FROM values_and_receipts').fetchone()[0],
                      'writes': db.execute('SELECT count(*) FROM requests').fetchone()[0]}
        assert counts == {'objects': 1, 'writes': 1}, counts
        report.update(action_id=rows[0][0], connector_digest=rows[0][2], approvals=1, provider_counts=counts)
        return report
    finally:
        model.shutdown(); model.server_close(); thread.join(5)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = demonstration(codex_reuse)
    report['command'] = 'python3 -m tests.demo_gate5_reuse'
    (OUTPUT / 'reuse-demonstration.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'failed': report['failed']}))
    return 0 if report['failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
