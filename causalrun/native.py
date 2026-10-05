"""Local OpenCode service lifecycle and narrowly scoped preparation endpoints."""
import argparse
import fcntl
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit
from . import generation, runtime, storage, validation
from .contracts import Rejected, canonical, digest
from .server import RuntimeHandler, create_server
from .transport import request

BINDINGS = 'CREATE TABLE IF NOT EXISTS native_bindings (scope TEXT PRIMARY KEY, digest TEXT NOT NULL REFERENCES connectors(digest))'


def scope(inputs):
    operation = inputs.get('operation')
    if operation == 'github.issue.create.v1':
        repository = inputs.get('repository')
        if not isinstance(repository, str) or not repository:
            raise Rejected('Provide the GitHub owner/repository', 400)
        return {'operation': operation, 'repository': repository}
    if operation == 'controlled.value.create.v1':
        target = inputs.get('target')
        url = urlsplit(target or '')
        if (url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port
                or url.path or url.query or url.fragment or url.username or url.password):
            raise Rejected('Controlled targets must be a loopback origin', 400)
        return {'operation': operation, 'target': target}
    raise Rejected('No connector for this operation; no write was sent', 400)


def binding(path, inputs, author=None):
    fields = scope(inputs)
    clarify_success = inputs.get('needs_success_clarification', False)
    if type(clarify_success) is not bool:
        raise Rejected('needs_success_clarification must be a boolean', 400)
    with storage.connect(path) as db:
        row = db.execute('SELECT digest FROM native_bindings WHERE scope=?', (digest(fields),)).fetchone()
        if row and not clarify_success:
            try:
                artifact = runtime.preflight(db, row['digest'])
                if artifact['schema_version'] == 3 and artifact['author'] != author:
                    raise Rejected('GitHub identity changed; prepare and review again')
                return {'ready': True, 'connector_digest': row['digest'], 'scope': fields,
                        'expected': artifact['expected'], 'limitations': artifact['limitations']}
            except Rejected:
                pass
    return {'ready': False, 'scope': fields, **preparation_guide(fields, author, clarify_success)}



def preparation_guide(fields, author, clarify_success=False):
    """Return actionable contract inputs, not a saved discovery report."""
    if fields['operation'] == 'controlled.value.create.v1':
        from .discovery import questions
        prompts = questions()
        sources = [fields['target'] + '/openapi.json']
        expected_fields = 'action_id, payload_digest, result.value matching payload.value'
        authentication = 'Explicit controlled write token and distinct receipt-read token'
    else:
        repository = fields['repository']
        prompts = [
            {'id': 'expected_behavior', 'title': 'What observable result should count as success?',
             'options': ['Create one issue with the requested title and body under the approved author'], 'free_text': True},
            {'id': 'sandbox', 'title': 'Confirm the repository this connector may write to; validation uses a local fixture.',
             'options': ['Dedicated repository: ' + repository, 'Stop before preparing this connector'], 'free_text': True},
            {'id': 'unknown_policy', 'title': 'If evidence is inconclusive, should the action stay blocked?',
             'options': ['Keep uncertain actions blocked', 'Stop before preparing this connector'], 'free_text': True},
            {'id': 'marker_assumption', 'title': 'Marker matching assumes the approved author does not copy or edit markers during recovery. Accept this limit?',
             'options': ['Accepted: no copied or edited markers during recovery', 'Stop before preparing this connector'], 'free_text': True},
        ]
        sources = ['https://docs.github.com/en/rest/issues/issues',
                   'https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api']
        expected_fields = 'action_id, payload_digest, result.title and result.body matching the payload; adapter also checks repository and creator'
        authentication = 'Local gh auth or GH_TOKEN/GITHUB_TOKEN; issue write and read permissions'
    # These supported profiles have synchronous, documented creation semantics.
    # The host must flag a request whose intent adds an unresolved business choice.
    documented_success = prompts[0]['options'][0]
    success_question = prompts[0]
    if not clarify_success:
        prompts = prompts[1:]
    return {'next': 'Discover the API, ask only missing user intent, generate source, then prepare and review',
            'discovery_sources': sources, 'authentication': authentication, 'github_author': author,
            'questions': prompts, 'prepare_fields': ['operation', 'repository or target', 'source', 'answers', 'api_version for controlled profile'],
            'documented_success': {'expected_behavior': documented_success, 'sources': sources,
                                   'origin': 'API profile, not a user answer'},
            'success_clarification': success_question,
            'answers_format': 'Exact answers for unresolved questions. Omit expected_behavior to use documented success; never fabricate sandbox or marker consent.',
            'intent_rule': 'Read documentation and existing user request first. Ask success_clarification only if a material ambiguity remains; then set needs_success_clarification=true and supply the actual answer. Do not ask the user to restate documented behavior.',
            'verifier_contract': {'signature': 'def verify(action_id, payload, evidence)',
                                  'expected_fields': expected_fields,
                                  'helpers': 'digest(payload), isinstance(value, dict)',
                                  'language': 'One pure boolean return expression; dictionary subscripts, membership, comparisons, boolean operations; no imports, attributes, network, loops, or assignments',
                                  'false_means': 'Unknown; never failure'}}

def prepare(path, inputs, author):
    fields = scope(inputs)
    source, answers = inputs.get('source'), inputs.get('answers')
    if not isinstance(source, str) or not isinstance(answers, dict):
        raise Rejected('Host-agent verifier source and completed user answers are required', 400)
    clarify_success = inputs.get('needs_success_clarification', False)
    if type(clarify_success) is not bool:
        raise Rejected('needs_success_clarification must be a boolean', 400)
    answers = dict(answers)
    if 'expected_behavior' not in answers:
        if clarify_success:
            raise Rejected('Resolve the success ambiguity before preparation', 400)
        answers['expected_behavior'] = preparation_guide(fields, author)['documented_success']['expected_behavior']
    if fields['operation'] == 'github.issue.create.v1':
        if not author:
            raise Rejected('Configure GitHub authentication locally before preparation', 400)
        artifact = generation.build_github_contract(fields['repository'], author, source, answers)
    else:
        target = fields['target']
        artifact = generation.build_contract({
            'target': target, 'source': target + '/openapi.json', 'operation_id': 'createValue',
            'api_version': inputs.get('api_version'), 'answers': answers}, source)
    identifier = runtime.register(path, artifact)
    report = validation.validate(path, identifier)
    return {'scope': fields, 'connector_digest': identifier, 'report_digest': digest(report),
            'artifact': artifact, 'validation': report, 'ready': False}


class NativeHandler(RuntimeHandler):
    def check_scope(self, inputs):
        fields = scope(inputs)
        if fields['operation'] != self.server.credential_operation:
            raise Rejected('Configured credentials are for another provider profile', 400)
        return fields

    def check_credentials(self, artifact):
        super().check_credentials(artifact)
        self.check_scope(artifact)
        if artifact['schema_version'] == 3 and (not self.server.github_author or artifact['author'] != self.server.github_author):
            raise Rejected('GitHub identity unavailable or changed; prepare and review again')

    def dispatch(self):
        if self.path == '/native/approve' and self.command == 'POST':
            self.authorized(self.server.operator_token)
            body = self.read_json()
            if set(body) != {'connector_digest', 'report_digest', 'scope'}:
                raise Rejected('Approve only the exact displayed contract and report', 400)
            identifier = body['connector_digest']
            fields = self.check_scope(body['scope'])
            with storage.connect(self.server.db_path) as db:
                artifact = runtime.load_connector(db, identifier)
            actual = {'operation': artifact['operation']}
            if artifact['schema_version'] == 3:
                actual['repository'] = artifact['repository']
            else:
                actual['target'] = artifact['target']
            if actual != fields:
                raise Rejected('Approval scope does not match artifact', 400)
            runtime.approve(self.server.db_path, identifier, identifier, body['report_digest'])
            with storage.connect(self.server.db_path) as db:
                db.execute('INSERT OR REPLACE INTO native_bindings VALUES(?,?)', (digest(fields), identifier))
            return binding(self.server.db_path, fields, self.server.github_author)
        if self.path.startswith('/native/'):
            self.authorized(self.server.agent_token)
            if self.command == 'POST' and self.path == '/native/status':
                if self.read_json() != {}:
                    raise Rejected('Status accepts no overrides', 400)
                return {'instance': self.server.instance, 'pid': os.getpid(), 'github_author': self.server.github_author}
            if self.command == 'POST' and self.path == '/native/lookup':
                inputs = self.read_json()
                self.check_scope(inputs)
                return binding(self.server.db_path, inputs, self.server.github_author)
            if self.command == 'POST' and self.path == '/native/prepare':
                inputs = self.read_json()
                self.check_scope(inputs)
                review = prepare(self.server.db_path, inputs, self.server.github_author)
                directory = Path(self.server.db_path).parent / 'reviews'
                directory.mkdir(mode=0o700, exist_ok=True)
                os.chmod(directory, 0o700)
                path = directory / (review['connector_digest'] + '-' + review['report_digest'] + '.json')
                private_json(path, review)
                return dict(review, review_file=str(path))
            raise Rejected('Unknown native endpoint', 404)
        return super().dispatch()


def private_json(path, value):
    temporary = path.with_suffix('.tmp')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(canonical(value))
    os.replace(temporary, path)


def serve(state):
    credentials = json.loads((state / 'capabilities.json').read_text())
    provider = os.environ.get('CAUSALRUN_PROVIDER_TOKEN') or os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    author = None
    if not provider:
        try:
            provider = subprocess.check_output(['gh', 'auth', 'token', '--hostname', 'github.com'],
                                               text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            provider = secrets.token_hex(24)
    # A controlled-fixture credential is explicitly configured by the test/operator.
    if not os.environ.get('CAUSALRUN_PROVIDER_TOKEN'):
        try:
            _, user = request('https://api.github.com', '/user', provider)
            author = user['login']
        except Exception:
            pass
    db_path = str(state / 'runtime.sqlite')
    storage.initialize(db_path)
    with storage.connect(db_path) as db:
        db.execute(BINDINGS)
    server = create_server(db_path, 0, credentials['agent_token'], provider,
                           os.environ.get('CAUSALRUN_RECEIPT_TOKEN'))
    server.RequestHandlerClass = NativeHandler
    server.operator_token = credentials['operator_token']
    server.github_author = author
    server.credential_operation = ('controlled.value.create.v1' if os.environ.get('CAUSALRUN_PROVIDER_TOKEN')
                                   else 'github.issue.create.v1')
    server.instance = secrets.token_hex(24)
    private_json(state / 'service.json', {'url': 'http://127.0.0.1:' + str(server.server_port),
                                        'instance': server.instance, 'pid': os.getpid()})
    try:
        server.serve_forever()
    finally:
        server.server_close()



def running(state):
    """Authenticate the recorded instance before trusting its URL or PID."""
    try:
        credentials = json.loads((state / 'capabilities.json').read_text())
        service = json.loads((state / 'service.json').read_text())
        url = urlsplit(service['url'])
        if (url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port or url.path
                or url.username or url.password or url.query or url.fragment):
            return None
        _, health = request(service['url'], '/native/status', credentials['agent_token'], {})
        if health['instance'] == service['instance'] and health['pid'] == service['pid']:
            return dict(service, **credentials)
    except Exception:
        pass
    return None


def stop(state):
    import signal
    service = running(state)
    if service is None:
        return {'stopped': False}
    os.kill(service['pid'], signal.SIGTERM)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if running(state) is None:
            return {'stopped': True}
        time.sleep(0.1)
    raise Rejected('The authenticated local service did not stop')

def ensure(state):
    state.mkdir(parents=True, exist_ok=True)
    os.chmod(state, 0o700)
    lock_fd = os.open(state / 'service.lock', os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(lock_fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        credential_path = state / 'capabilities.json'
        if not credential_path.exists():
            private_json(credential_path, {'agent_token': secrets.token_hex(24), 'operator_token': secrets.token_hex(24)})
        credentials = json.loads(credential_path.read_text())

        service = running(state)
        if service:
            return service
        log_fd = os.open(state / 'service.log', os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(log_fd, 'a') as log:
            subprocess.Popen([sys.executable, '-m', 'causalrun.native', 'serve', '--state', str(state)],
                             stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                             cwd=Path(__file__).resolve().parents[1], start_new_session=True)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            service = running(state)
            if service:
                return service
            time.sleep(0.1)
        raise Rejected('Local runtime did not become ready; inspect the private service log')



def review(state, identifier):
    """MCP clients can prepare; only this separate operator terminal can approve."""
    if not sys.stdin.isatty():
        raise Rejected('Connector review requires an interactive operator terminal')
    service = ensure(state)
    with storage.connect(str(state / 'runtime.sqlite')) as db:
        artifact = runtime.load_connector(db, identifier)
        record = db.execute('SELECT report,report_digest FROM validations WHERE digest=?', (identifier,)).fetchone()
    if record is None:
        raise Rejected('Validate before review')
    print(json.dumps({'connector': artifact, 'validation': json.loads(record['report'])}, indent=2))
    confirmation = input('Type the full connector digest to approve: ').strip()
    if confirmation != identifier:
        raise Rejected('Approval confirmation must match the exact connector digest')
    fields = {'operation': artifact['operation']}
    fields['repository' if artifact['schema_version'] == 3 else 'target'] = artifact.get('repository', artifact['target'])
    _, approved = request(service['url'], '/native/approve', service['operator_token'], {
        'connector_digest': identifier, 'report_digest': record['report_digest'], 'scope': fields})
    return approved

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('ensure', 'serve', 'stop', 'review'))
    parser.add_argument('--state', required=True)
    parser.add_argument('--digest')
    args = parser.parse_args()
    state = Path(args.state).resolve()
    if args.command == 'serve':
        serve(state)
    elif args.command == 'review':
        if not args.digest:
            parser.error('Review requires --digest')
        try:
            print(canonical(review(state, args.digest)))
        except Rejected as error:
            print(str(error), file=sys.stderr)
            raise SystemExit(1)
    elif args.command == 'stop':
        print(canonical(stop(state)))
    else:
        print(canonical(ensure(state)))


if __name__ == '__main__':
    main()
