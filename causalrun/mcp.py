"""Small stdio MCP adapter. Preparation is allowed; approval is operator-only."""
import argparse
import json
import sys
from pathlib import Path
from urllib.parse import quote
from . import native
from .contracts import Rejected, canonical
from .transport import request

VERSIONS = ('2024-11-05', '2025-03-26', '2025-06-18', '2025-11-25')
SCOPE = {'operation': {'type': 'string', 'enum': ['controlled.value.create.v1', 'github.issue.create.v1']},
         'needs_success_clarification': {'type': 'boolean', 'description': 'True when API docs and user request leave material success ambiguity; resolve before prepare'},
         'target': {'type': 'string', 'description': 'Controlled loopback origin only'},
         'repository': {'type': 'string', 'description': 'GitHub owner/repository'}}
STRINGS = {'type': 'object', 'additionalProperties': {'type': 'string'}}
TOOLS = [
    {'name': 'causalrun_lookup', 'description': 'Inspect approval or receive API discovery and user-question guidance. No write.',
     'properties': SCOPE, 'required': ['operation'], 'read_only': True},
    {'name': 'causalrun_prepare', 'description': 'Package host-agent-written pure verifier and actual user answers; validate only in disposable fixtures. Returns an exact review for operator approval. No approval tool exists.',
     'properties': dict(SCOPE, source={'type': 'string'}, answers=STRINGS, api_version={'type': 'string'}),
     'required': ['operation', 'source', 'answers'], 'read_only': False},
    {'name': 'causalrun_write', 'description': 'Dispatch only an approved connector. Reuse the same action_key and payload across retries and harnesses. IN_DOUBT never resends.',
     'properties': dict(SCOPE, action_key={'type': 'string'}, payload=STRINGS),
     'required': ['operation', 'action_key', 'payload'], 'read_only': False},
    {'name': 'causalrun_verify', 'description': 'Read-only evidence check for the original action. Missing evidence means unknown, never failure.',
     'properties': {'action_id': {'type': 'string'}}, 'required': ['action_id'], 'read_only': True},
    {'name': 'causalrun_result', 'description': 'Read the saved result and timeline without contacting the provider.',
     'properties': {'action_id': {'type': 'string'}}, 'required': ['action_id'], 'read_only': True},
]


class ProtocolError(Exception):
    def __init__(self, code, message):
        self.code, self.message = code, message


class Adapter:
    def __init__(self, state):
        self.state = Path(state).resolve()
        self.initialized = False
        self.ready = False

    def api(self, path, body=None):
        service = native.ensure(self.state)
        # Operator capabilities are never exposed through the tool interface.
        _, result = request(service['url'], path, service['agent_token'], body)
        return result

    def call(self, name, arguments):
        definition = next((tool for tool in TOOLS if tool['name'] == name), None)
        if definition is None:
            raise ProtocolError(-32602, 'Unknown tool')
        if (not isinstance(arguments, dict) or not set(definition['required']) <= set(arguments)
                or not set(arguments) <= set(definition['properties'])):
            raise ProtocolError(-32602, 'Unsupported or missing tool fields')
        for field, value in arguments.items():
            schema = definition['properties'][field]
            if schema['type'] == 'string' and not isinstance(value, str):
                raise ProtocolError(-32602, 'Expected string field')
            if schema['type'] == 'boolean' and type(value) is not bool:
                raise ProtocolError(-32602, 'Expected boolean field')
            if schema['type'] == 'object' and (not isinstance(value, dict) or
                                               not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items())):
                raise ProtocolError(-32602, 'Expected string-valued object')
            if 'enum' in schema and value not in schema['enum']:
                raise ProtocolError(-32602, 'Unsupported operation')
        try:
            if name == 'causalrun_lookup':
                value = self.api('/native/lookup', arguments)
            elif name == 'causalrun_prepare':
                value = self.api('/native/prepare', arguments)
                value['status'] = 'VALIDATION_FAILED' if value['validation']['failed'] else 'REVIEW_REQUIRED'
                value['operator_review'] = {'command': 'python3', 'args': ['causalrun.pyz', '--review', value['connector_digest'], '--state-dir', str(self.state)],
                                            'instruction': 'Run only in a separate trusted operator terminal; the agent must not approve itself'}
            elif name == 'causalrun_write':
                lookup = self.api('/native/lookup', {k: v for k, v in arguments.items() if k in SCOPE})
                if not lookup['ready']:
                    value = dict(lookup, status='PREPARATION_REQUIRED')
                else:
                    value = self.api('/v1/actions', {'connector_digest': lookup['connector_digest'],
                                                    'action_key': arguments['action_key'], 'payload': arguments['payload']})
            else:
                path = '/v1/actions/' + quote(arguments['action_id'], safe='')
                value = self.api(path + '/verify', {}) if name == 'causalrun_verify' else self.api(path)
            return {'content': [{'type': 'text', 'text': canonical(value)}], 'structuredContent': value, 'isError': False}
        except Exception:
            # Provider exceptions and credentials must never enter model-visible errors.
            return {'content': [{'type': 'text', 'text': 'Runtime rejected or could not confirm this request. Inspect the original action; do not invent a new key or repeat a provider write.'}], 'isError': True}

    def dispatch(self, message):
        if (not isinstance(message, dict) or message.get('jsonrpc') != '2.0'
                or not isinstance(message.get('method'), str)
                or ('id' in message and type(message['id']) not in (str, int))):
            raise ProtocolError(-32600, 'Invalid request')
        method, params = message['method'], message.get('params', {})
        if not isinstance(params, dict):
            raise ProtocolError(-32602, 'Expected object parameters')
        if method == 'initialize':
            if self.initialized:
                raise ProtocolError(-32600, 'Already initialized')
            if not isinstance(params.get('protocolVersion'), str) or not isinstance(params.get('capabilities'), dict) or not isinstance(params.get('clientInfo'), dict):
                raise ProtocolError(-32602, 'Initialize requires version, capabilities, and clientInfo')
            self.initialized = True
            version = params['protocolVersion'] if params['protocolVersion'] in VERSIONS else VERSIONS[-1]
            return {'protocolVersion': version, 'capabilities': {'tools': {'listChanged': False}},
                    'serverInfo': {'name': 'causalrun', 'version': '1.0.0'},
                    'instructions': 'Discover API behavior, ask actual user intent, generate and validate before any write. Connector approval belongs to a separate trusted operator terminal; never approve yourself. Reuse original action keys across harnesses. Uncertain outcomes stay blocked.'}
        if method == 'notifications/initialized' and self.initialized:
            self.ready = True
            return None
        if method == 'ping':
            return {}
        if 'id' not in message:
            return None
        if not self.ready:
            raise ProtocolError(-32600, 'Complete initialization before using tools')
        if method == 'tools/list':
            if not set(params) <= {'cursor', '_meta'} or params.get('cursor') is not None:
                raise ProtocolError(-32602, 'This fixed tool list has no next-page cursor')
            return {'tools': [{'name': tool['name'], 'description': tool['description'],
                              'inputSchema': {'type': 'object', 'properties': tool['properties'],
                                              'required': tool['required'], 'additionalProperties': False},
                              'annotations': {'readOnlyHint': tool['read_only']}} for tool in TOOLS]}
        if method == 'tools/call':
            if not set(params) <= {'name', 'arguments', '_meta'} or not isinstance(params.get('name'), str):
                raise ProtocolError(-32602, 'Tool name and supported call fields required')
            return self.call(params['name'], params.get('arguments', {}))
        raise ProtocolError(-32601, 'Method not found')

    def process(self, line):
        identifier, notification = None, False
        try:
            if len(line.encode()) > 16384:
                raise ProtocolError(-32600, 'Message exceeds 16 KiB')
            try:
                message = json.loads(line)
            except ValueError:
                raise ProtocolError(-32700, 'Parse error')
            if isinstance(message, dict):
                identifier = message.get('id') if type(message.get('id')) in (str, int) else None
                notification = 'id' not in message and message.get('jsonrpc') == '2.0' and isinstance(message.get('method'), str)
            result = self.dispatch(message)
            return None if notification else {'jsonrpc': '2.0', 'id': identifier, 'result': result}
        except ProtocolError as error:
            return None if notification else {'jsonrpc': '2.0', 'id': identifier, 'error': {'code': error.code, 'message': error.message}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state', default=str(Path.home() / '.local/share/causalrun'))
    args = parser.parse_args()
    adapter = Adapter(args.state)
    while True:
        line = sys.stdin.readline(16385)
        if not line:
            break
        if not line.endswith('\n'):
            # Drain an oversized frame before parsing the next JSON-RPC message.
            while line and not line.endswith('\n'):
                line = sys.stdin.readline(16385)
            response = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32600, 'message': 'Message exceeds 16 KiB'}}
        else:
            response = adapter.process(line)
        if response is not None:
            print(canonical(response), flush=True)


if __name__ == '__main__':
    main()
