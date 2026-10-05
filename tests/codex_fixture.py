"""Local Responses-wire fixture for an actual Codex CLI; no model inference."""
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def create_model(target, action_key):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            server = self.server
            server.inputs.append(body.get('input', []))
            names = []
            for tool in body.get('tools', []):
                if tool.get('type') == 'namespace':
                    names.extend(tool['name'] + '.' + child['name'] for child in tool.get('tools', []))
                else:
                    names.append(tool.get('name', ''))
            server.advertised_tools = names
            step = server.step; server.step += 1
            call = None
            if step == 0:
                call = ('causalrun_write', {'operation': 'controlled.value.create.v1', 'target': target,
                                           'action_key': action_key, 'payload': {'value': 'OpenCode durable value'}})
            elif step == 1:
                text = json.dumps(body.get('input', []))
                ids = re.findall(r'"id"\s*:\s*"([a-f0-9-]{36})"', text.replace('\\"', '"'))
                if ids: server.action_id = ids[-1]
                call = ('causalrun_result', {'action_id': server.action_id or 'missing'})
            elif step == 2:
                call = ('causalrun_verify', {'action_id': server.action_id or 'missing'})
            if call:
                short, arguments = call
                name = next((n for n in names if n.endswith(short)), None)
                if name:
                    item = {'type': 'function_call', 'id': 'fc_' + str(step), 'call_id': 'call_' + str(step),
                            'name': name, 'arguments': json.dumps(arguments)}
                    if '.' in name:
                        item['namespace'], item['name'] = name.split('.', 1)
                else:
                    call = None
                    server.failure = 'MCP tool not advertised: ' + short
            if not call:
                item = {'type': 'message', 'id': 'msg_' + str(step), 'role': 'assistant', 'status': 'completed',
                        'content': [{'type': 'output_text', 'text': 'Codex MCP acceptance fixture complete.', 'annotations': []}]}
            server.calls.append({'step': step, 'tool': item.get('name'), 'arguments': call[1] if call else None})
            self.send_response(200); self.send_header('Content-Type', 'text/event-stream'); self.end_headers()
            response = {'id': 'resp_' + str(step), 'object': 'response', 'status': 'in_progress', 'output': []}
            events = [{'type': 'response.created', 'response': response},
                      {'type': 'response.output_item.added', 'output_index': 0, 'item': dict(item, arguments='') if call else item}]
            if call:
                events += [{'type': 'response.function_call_arguments.delta', 'item_id': item['id'], 'output_index': 0, 'delta': item['arguments']},
                           {'type': 'response.function_call_arguments.done', 'item_id': item['id'], 'output_index': 0, 'arguments': item['arguments']}]
            else:
                events += [{'type': 'response.output_text.delta', 'item_id': item['id'], 'output_index': 0, 'content_index': 0,
                            'delta': item['content'][0]['text']}]
            events += [{'type': 'response.output_item.done', 'output_index': 0, 'item': item},
                       {'type': 'response.completed', 'response': dict(response, status='completed', output=[item],
                         usage={'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2})}]
            for index, event in enumerate(events):
                event['sequence_number'] = index
                self.wfile.write(('event: ' + event['type'] + '\ndata: ' + json.dumps(event) + '\n\n').encode())
            self.wfile.flush(); self.close_connection = True
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.step = 0; server.calls = []; server.inputs = []; server.advertised_tools = []; server.action_id = None; server.failure = None
    return server
