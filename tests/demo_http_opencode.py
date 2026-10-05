"""Actual fresh OpenCode, crash/restart, and stdio MCP generic action replay."""
from tests.demo_gate4 import demonstration
from tests.mcp_client import Client
from tests.opencode_fixture import create_model


def demonstrate_host():
    def second_harness(folder, state, target, action, env):
        client = Client(state, env=env)
        try:
            replay = client.call('causalrun_write', {
                'operation': 'http.json.write.v1', 'name': 'fixture-entry', 'target': target,
                'action_key': 'opencode-acceptance-write', 'payload': {'value': 'OpenCode durable value'}})
            assert not replay['isError'], replay
            saved = client.call('causalrun_result', {'action_id': action[0]})
            assert not saved['isError'], saved
            assert replay['structuredContent']['id'] == saved['structuredContent']['id'] == action[0]
            assert saved['structuredContent']['state'] == 'COMMITTED'
            return {'protocol': 'Actual newline JSON-RPC stdio subprocess',
                    'same_action': True, 'result': saved['structuredContent']}
        finally:
            client.close()
    return demonstration(model_factory=lambda target: create_model(target, generic=True),
                         generic=True, global_config=True, new_session_probe=True,
                         after_restart=second_harness)
