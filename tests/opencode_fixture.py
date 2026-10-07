"""Scripted model protocol for real OpenCode acceptance, with no paid inference."""
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / 'examples/verify_value.py').read_text()


def create_model(target, repair=False, selective=False, ambiguous=False, generic=False, load_skill=False):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200); self.end_headers(); self.wfile.write(b'{"data":[]}')

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            server = self.server
            call = None
            if body.get('tools'):
                step = server.step
                server.step += 1
                if load_skill:
                    step -= 1
                if repair and step >= 5:
                    step -= 1
                common = {'operation': 'controlled.value.create.v1', 'target': target}
                write = dict(common, action_key='opencode-acceptance-write', payload={'value': 'OpenCode durable value'})
                if step == 0:
                    call = ('http_request', {'method': 'POST', 'url': target + '/values'})
                elif step == 1:
                    call = ('causalrun_write', dict(write, needs_success_clarification=True) if ambiguous else write)
                elif step == 2:
                    call = ('webfetch', {'url': target + '/openapi.json', 'format': 'text'})
                elif step == 3:
                    questions = [
                        {'header': 'Result', 'question': 'What should count as success?',
                         'options': [{'label': 'Exact value', 'description': 'Value and original identity must match'}]},
                        {'header': 'Sandbox', 'question': 'May validation use a disposable local fixture?',
                         'options': [{'label': 'Fixture only', 'description': 'No configured-target validation writes'}]},
                        {'header': 'Unknown', 'question': 'How should inconclusive evidence be handled?',
                         'options': [{'label': 'Keep blocked', 'description': 'Request review without resending'}]},
                    ]
                    if selective and not ambiguous:
                        questions = questions[1:]
                    call = ('question', {'questions': questions})
                elif step == 4:
                    source = 'def verify(action_id, payload, evidence):\n    return True\n' if repair and server.step == 5 else SOURCE
                    call = ('causalrun_prepare', dict(common, api_version='1', source=source, answers={
                        'expected_behavior': 'The returned value must exactly match payload.value',
                        'sandbox': 'Yes, only the disposable fixture', 'unknown_policy': 'Keep blocked and request review'}))
                    if selective and not ambiguous:
                        del call[1]['answers']['expected_behavior']
                    if ambiguous:
                        call[1]['needs_success_clarification'] = True
                elif step == 5:
                    call = ('causalrun_write', write)
                elif step == 6:
                    # Read the actual action identity from the tool's JSON output.
                    identifiers = re.findall(r'"id"\s*:\s*"([0-9a-f-]{36})"', json.dumps(body['messages']).replace('\\"', '"'))
                    if not identifiers:
                        raise AssertionError('No durable action identity in model context')
                    server.action_id = identifiers[-1]
                    call = ('causalrun_verify', {'action_id': server.action_id})
                elif step == 7:
                    call = ('causalrun_write', write)
                elif step == 8:
                    call = ('causalrun_result', {'action_id': server.action_id})
                elif step == 10:
                    call = ('causalrun_write', write)
                elif step == 11:
                    call = ('causalrun_result', {'action_id': server.action_id})
                if generic:
                    from tests.test_http_json import artifact
                    contract = artifact(target)
                    common = {'operation': 'http.json.write.v1', 'target': target, 'name': contract['name']}
                    write = dict(common, action_key='opencode-acceptance-write', payload={'value': 'OpenCode durable value'})
                    if step == 0:
                        call = ('http_request', {'method': 'POST', 'url': target + '/entries'})
                    elif step == 1:
                        call = ('causalrun_write', write)
                    elif step == 2:
                        call = ('webfetch', {'url': target + '/openapi.json', 'format': 'text'})
                    elif step == 3:
                        call = ('causalrun_prepare', dict(common, source=contract['verifier']['source'], answers={}, contract=contract))
                    elif step in (4, 6, 9):
                        call = ('causalrun_write', write)
                    elif step == 5:
                        identifiers = re.findall(r'"id"\s*:\s*"([0-9a-f-]{36})"', json.dumps(body['messages']).replace('\\"', '"'))
                        if not identifiers:
                            raise AssertionError('No generic durable action identity')
                        server.action_id = identifiers[-1]
                        call = ('causalrun_verify', {'action_id': server.action_id})
                    elif step in (7, 10):
                        call = ('causalrun_result', {'action_id': server.action_id})
                    else:
                        call = None
                if load_skill and step == -1:
                    skills = [item for item in body['tools'] if item.get('function', {}).get('name') == 'skill']
                    server.skill_diagnostics = {
                        'tool_names': [item.get('function', {}).get('name', item.get('name')) for item in body['tools']],
                        'skill_tool_present': bool(skills),
                        'description_includes_name': bool(skills and 'causalrun' in skills[0]['function'].get('description', '')),
                        'parameters_include_name': bool(skills and 'causalrun' in json.dumps(skills[0]['function'].get('parameters', {}))),
                        'description_in_messages': 'Use causalrun for external API writes requested in ordinary development tasks' in json.dumps(body['messages']),
                        'parameters': skills[0]['function'].get('parameters', {}) if skills else {},
                        'description': skills[0]['function'].get('description', '') if skills else '',
                    }
                    advertised = (server.skill_diagnostics['description_includes_name']
                                  or server.skill_diagnostics['description_in_messages'])
                    assert skills and advertised, 'Skill not advertised to the model'
                    server.skill_advertised = advertised
                    call = ('skill', {'name': 'causalrun'})
                server.calls.append({'step': step, 'tool': call[0] if call else None})
            message = {'role': 'assistant', 'content': 'Acceptance fixture complete.' if call is None else None}
            if call:
                name, arguments = call
                message['tool_calls'] = [{'id': 'fixture-call-' + str(server.step), 'type': 'function',
                                          'function': {'name': name, 'arguments': json.dumps(arguments)}}]
            response = {'id': 'fixture-completion', 'object': 'chat.completion', 'created': 1,
                        'model': 'scripted', 'choices': [{'index': 0, 'message': message,
                                                       'finish_reason': 'tool_calls' if call else 'stop'}],
                        'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}
            # AI SDK requests streaming responses; use its ordinary SSE wire protocol.
            if body.get('stream'):
                self.send_response(200); self.send_header('Content-Type', 'text/event-stream'); self.end_headers()
                delta = dict(message); delta.pop('role', None)
                if call:
                    delta['tool_calls'][0]['index'] = 0
                chunk = dict(response, object='chat.completion.chunk', choices=[{'index': 0, 'delta': delta, 'finish_reason': None}])
                self.wfile.write(('data: ' + json.dumps(chunk) + '\n\n').encode())
                chunk['choices'] = [{'index': 0, 'delta': {}, 'finish_reason': 'tool_calls' if call else 'stop'}]
                self.wfile.write(('data: ' + json.dumps(chunk) + '\n\ndata: [DONE]\n\n').encode()); self.wfile.flush()
                self.close_connection = True
            else:
                data = json.dumps(response).encode()
                self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(data)))
                self.end_headers(); self.wfile.write(data)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.step = 0
    server.calls = []
    server.action_id = None
    server.skill_advertised = False
    server.skill_diagnostics = {}
    return server
