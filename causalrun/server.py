"""Agent-facing API: execution and inspection only; no approval endpoint."""
import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from . import runtime
from .contracts import Rejected


class JSONHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def send_json(self, status, value):
        data = json.dumps(value, allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def read_json(self):
        length = int(self.headers.get('Content-Length', '0'))
        if not 0 < length <= 16384:
            raise Rejected('A JSON body up to 16 KiB is required', 400)
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict):
            raise Rejected('Expected a JSON object', 400)
        return value

    def authorized(self, token):
        if not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token):
            raise Rejected('Unauthorized', 401)

    def do_GET(self):
        self.handle_call()

    def do_POST(self):
        self.handle_call()

    def handle_call(self):
        try:
            self.send_json(200, self.dispatch())
        except (ConnectionAbortedError, BrokenPipeError, ConnectionResetError):
            return
        except Rejected as error:
            self.send_json(error.status, {'error': str(error)})
        except (ValueError, TypeError, KeyError):
            self.send_json(400, {'error': 'Invalid request'})
        except Exception:
            self.send_json(500, {'error': 'Internal error; inspect the recorded action before further work'})


class RuntimeHandler(JSONHandler):
    def check_credentials(self, artifact):
        if not self.server.receipt_credentials_configured and artifact['schema_version'] == 2:
            raise Rejected('Generated connectors require distinct receipt credentials', 400)

    def dispatch(self):
        if self.command == 'GET' and self.path == '/health':
            return {'status': 'ready'}
        self.authorized(self.server.agent_token)
        if self.command == 'POST' and self.path == '/v1/actions':
            body = self.read_json()
            if set(body) != {'connector_digest', 'action_key', 'payload'}:
                raise Rejected('Only connector_digest, action_key, and payload are accepted', 400)
            from . import storage
            with storage.connect(self.server.db_path) as db:
                artifact = runtime.load_connector(db, body['connector_digest'])
            self.check_credentials(artifact)
            return runtime.execute(self.server.db_path, body['connector_digest'],
                                   body['action_key'], body['payload'], self.server.provider_token)
        parts = self.path.split('/')
        if len(parts) in (4, 5) and parts[1:3] == ['v1', 'actions']:
            if self.command == 'GET' and len(parts) == 4:
                return runtime.result(self.server.db_path, parts[3])
            if self.command == 'POST' and len(parts) == 5 and parts[4] == 'verify':
                if self.read_json() != {}:
                    raise Rejected('Verification accepts no overrides', 400)
                action = runtime.result(self.server.db_path, parts[3])
                if action['state'] != 'COMMITTED':
                    from . import storage
                    with storage.connect(self.server.db_path) as db:
                        artifact = runtime.load_connector(db, action['connector_digest'])
                    self.check_credentials(artifact)
                return runtime.verify(self.server.db_path, parts[3], self.server.receipt_token)
        raise Rejected('Endpoint not found', 404)


def create_server(path, port, agent_token, provider_token, receipt_token=None):
    if len(agent_token) < 16 or len(provider_token) < 16:
        raise Rejected('Agent and provider tokens must each have at least 16 characters', 400)
    if agent_token == provider_token:
        raise Rejected('Agent and provider tokens must differ', 400)
    if receipt_token is not None and (len(receipt_token) < 16 or receipt_token in (agent_token, provider_token)):
        raise Rejected('Receipt credential must be distinct and at least 16 characters', 400)
    server = ThreadingHTTPServer(('127.0.0.1', port), RuntimeHandler)
    server.db_path = path
    server.agent_token = agent_token
    server.provider_token = provider_token
    server.receipt_token = receipt_token or provider_token
    server.receipt_credentials_configured = receipt_token is not None
    return server
