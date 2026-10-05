"""Real HTTP/SQLite boundary tests against a disposable controlled application."""
import copy
import json
import os
import pty
import select
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from causalrun import runtime, storage, validation
from causalrun.contracts import Rejected, canonical, digest, example_artifact
from causalrun.server import create_server
from causalrun.transport import request
from examples.provider import create_server as create_provider

AGENT_TOKEN = 'disposable-agent-capability'
PROVIDER_TOKEN = 'disposable-provider-capability'
ROOT = Path(__file__).resolve().parents[1]


def terminal_approval(db_path, identifier, confirmation=None, on_prompt=None, command=None):
    """Exercise the actual operator command in a pseudo-terminal."""
    master, slave = pty.openpty()
    process = subprocess.Popen(command or [sys.executable, '-m', 'causalrun', '--db', db_path,
                                'approve', identifier], cwd=ROOT,
                               stdin=slave, stdout=slave, stderr=slave, close_fds=True)
    os.close(slave)
    output = b''
    try:
        deadline = time.monotonic() + 10
        while b'Type the full connector digest to approve:' not in output:
            if time.monotonic() > deadline:
                raise AssertionError('Approval prompt not reached')
            if select.select([master], [], [], 0.2)[0]:
                try:
                    output += os.read(master, 65536)
                except OSError:
                    raise AssertionError(output.decode())
        if on_prompt:
            on_prompt()
        os.write(master, ((confirmation or identifier) + '\n').encode())
        while process.poll() is None:
            if time.monotonic() > deadline:
                raise AssertionError('Approval did not finish')
            if select.select([master], [], [], 0.2)[0]:
                try:
                    output += os.read(master, 65536)
                except OSError:
                    break
        return process.wait(timeout=5), output.decode()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = str(Path(self.directory.name) / 'runtime.sqlite')
        self.provider_db = str(Path(self.directory.name) / 'provider.sqlite')
        storage.initialize(self.db)
        self.provider = create_provider(self.provider_db, 0, PROVIDER_TOKEN)
        self.server = create_server(self.db, 0, AGENT_TOKEN, PROVIDER_TOKEN)
        for server in (self.provider, self.server):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(thread.join, 5)
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
        self.target = 'http://127.0.0.1:' + str(self.provider.server_port)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)
        self.artifact = example_artifact(self.target)
        self.identifier = runtime.register(self.db, self.artifact)

    def counts(self):
        with sqlite3.connect(self.provider_db) as db:
            return {'objects': db.execute('SELECT count(*) FROM values_and_receipts').fetchone()[0],
                    'writes': db.execute('SELECT count(*) FROM requests').fetchone()[0]}

    def ready(self):
        report = validation.validate(self.db, self.identifier)
        self.assertEqual((report['passed'], report['failed']), (4, 0))
        code, output = terminal_approval(self.db, self.identifier)
        self.assertEqual(code, 0, output)

    def execute(self, key='first', value='hello', identifier=None):
        return request(self.base, '/v1/actions', AGENT_TOKEN,
                       {'connector_digest': identifier or self.identifier,
                        'action_key': key, 'payload': {'value': value}})[1]

    def rejected(self, function, status):
        with self.assertRaises(HTTPError) as context:
            function()
        self.assertEqual(context.exception.code, status)
        return json.load(context.exception)['error']


class GateTests(Fixture):
    def test_missing_verifier_rejects_registration_and_write(self):
        artifact = copy.deepcopy(self.artifact)
        del artifact['verifier']
        with self.assertRaises(Rejected):
            runtime.register(self.db, artifact)
        self.rejected(lambda: self.execute(identifier=digest(artifact)), 404)
        self.assertEqual(self.counts(), {'objects': 0, 'writes': 0})

    def test_missing_validation_blocks_write(self):
        message = self.rejected(self.execute, 409)
        self.assertIn('Validated verifier', message)
        self.assertEqual(self.counts(), {'objects': 0, 'writes': 0})

    def test_missing_approval_blocks_write(self):
        validation.validate(self.db, self.identifier)
        self.assertIn('Approval', self.rejected(self.execute, 409))
        self.assertEqual(self.counts(), {'objects': 0, 'writes': 0})

    def test_terminal_approval_and_receipt_survive_reopen(self):
        self.ready()
        action = self.execute()
        self.assertEqual(action['state'], 'COMMITTED')
        self.assertEqual(action['receipt']['result'], {'value': 'hello'})
        self.assertEqual(self.counts(), {'objects': 1, 'writes': 1})
        storage.initialize(self.db)
        read = request(self.base, '/v1/actions/' + action['id'], AGENT_TOKEN)[1]
        self.assertEqual(read, action)
        self.assertEqual(self.execute(), action)
        self.assertEqual(self.counts(), {'objects': 1, 'writes': 1})
        self.assertEqual([event['kind'] for event in read['events']],
                         ['AUTHORIZED', 'RECEIPT_RECORDED'])

    def test_agent_cannot_approve_or_redirect_target(self):
        self.ready()
        self.rejected(lambda: request(self.base, '/v1/approve', AGENT_TOKEN,
                                      {'digest': self.identifier}), 404)
        self.rejected(lambda: request(self.base, '/v1/actions', AGENT_TOKEN,
                                      {'connector_digest': self.identifier, 'action_key': 'x',
                                       'payload': {'value': 'hello'}, 'target': self.target}), 400)
        self.rejected(lambda: request(self.base, '/v1/actions', PROVIDER_TOKEN,
                                      {'connector_digest': self.identifier, 'action_key': 'x',
                                       'payload': {'value': 'hello'}}), 401)
        self.assertEqual(self.counts(), {'objects': 0, 'writes': 0})

    def test_modified_artifact_and_target_invalidate_approval(self):
        self.ready()
        for field, value in [('target', 'http://127.0.0.1:1'), ('sources', ['different source'])]:
            artifact = copy.deepcopy(self.artifact)
            artifact[field] = value
            changed = runtime.register(self.db, artifact)
            self.rejected(lambda: self.execute(identifier=changed), 409)
            with storage.connect(self.db) as db:
                db.execute('UPDATE connectors SET artifact=? WHERE digest=?',
                           (canonical(artifact), self.identifier))
            self.rejected(self.execute, 409)
            with storage.connect(self.db) as db:
                db.execute('UPDATE connectors SET artifact=? WHERE digest=?',
                           (canonical(self.artifact), self.identifier))
        self.assertEqual(self.counts(), {'objects': 0, 'writes': 0})

    def test_changed_implementation_invalidates_approval(self):
        self.ready()
        with patch('causalrun.contracts.implementation_digest', return_value='changed'):
            self.rejected(self.execute, 409)
        self.assertEqual(self.counts(), {'objects': 0, 'writes': 0})

    def test_changed_validation_invalidates_approval(self):
        self.ready()
        validation.validate(self.db, self.identifier)
        self.rejected(self.execute, 409)
        self.assertEqual(self.counts(), {'objects': 0, 'writes': 0})

    def test_corrupted_validation_is_rejected(self):
        self.ready()
        with storage.connect(self.db) as db:
            db.execute("UPDATE validations SET report='{}' WHERE digest=?", (self.identifier,))
        self.rejected(self.execute, 409)
        self.assertEqual(self.counts(), {'objects': 0, 'writes': 0})

    def test_noninteractive_and_wrong_confirmation_rejected(self):
        validation.validate(self.db, self.identifier)
        command = [sys.executable, '-m', 'causalrun', '--db', self.db, 'approve', self.identifier]
        run = subprocess.run(command, input=self.identifier + '\n', capture_output=True, text=True)
        self.assertEqual(run.returncode, 1)
        self.assertIn('interactive operator terminal', run.stderr)
        code, output = terminal_approval(self.db, self.identifier, 'wrong digest')
        self.assertEqual(code, 1, output)
        self.rejected(self.execute, 409)
        self.assertEqual(self.counts(), {'objects': 0, 'writes': 0})

    def test_changed_payload_rejected(self):
        self.ready()
        self.execute()
        self.rejected(lambda: self.execute(value='changed'), 409)
        self.assertEqual(self.counts(), {'objects': 1, 'writes': 1})

    def test_concurrent_replays_send_once(self):
        self.ready()
        with ThreadPoolExecutor(max_workers=6) as pool:
            actions = list(pool.map(lambda _: self.execute(), range(12)))
        self.assertEqual(len({action['id'] for action in actions}), 1)
        self.assertEqual(self.counts(), {'objects': 1, 'writes': 1})
        self.assertEqual(runtime.result(self.db, actions[0]['id'])['state'], 'COMMITTED')

    def test_unconfirmed_write_is_not_resent(self):
        self.ready()
        real_request = runtime.request
        def lose_response(*args):
            real_request(*args)
            raise TimeoutError('injected after provider commit')
        with patch('causalrun.runtime.request', side_effect=lose_response):
            action = self.execute()
        self.assertEqual(action['state'], 'IN_DOUBT')
        self.assertEqual(self.execute()['id'], action['id'])
        self.assertEqual(self.counts(), {'objects': 1, 'writes': 1})
        verified = request(self.base, '/v1/actions/' + action['id'] + '/verify', AGENT_TOKEN, {})[1]
        self.assertEqual(verified['state'], 'COMMITTED')
        self.assertEqual(self.counts(), {'objects': 1, 'writes': 1})

    def test_failed_validation_cannot_be_approved(self):
        with patch('causalrun.validation.request', side_effect=TimeoutError('sandbox unavailable')):
            report = validation.validate(self.db, self.identifier)
        self.assertEqual(report['failed'], 1)
        code, output = terminal_approval(self.db, self.identifier)
        self.assertEqual(code, 1, output)
        self.rejected(self.execute, 409)
        self.assertEqual(self.counts(), {'objects': 0, 'writes': 0})

    def test_validation_changed_during_review_requires_new_approval(self):
        validation.validate(self.db, self.identifier)
        code, output = terminal_approval(
            self.db, self.identifier,
            on_prompt=lambda: validation.validate(self.db, self.identifier))
        self.assertEqual(code, 1, output)
        self.assertIn('Validation changed during review', output)
        self.rejected(self.execute, 409)
        self.assertEqual(self.counts(), {'objects': 0, 'writes': 0})

    def test_mismatched_receipt_remains_unknown(self):
        self.ready()
        with patch('causalrun.runtime.request', return_value=(200, {'unrelated': True})):
            action = self.execute()
        self.assertEqual(action['state'], 'IN_DOUBT')
        verified = request(self.base, '/v1/actions/' + action['id'] + '/verify', AGENT_TOKEN, {})[1]
        self.assertEqual(verified['state'], 'IN_DOUBT')
        self.assertEqual(self.execute()['id'], action['id'])
        self.assertEqual(self.counts(), {'objects': 0, 'writes': 0})

    def test_connector_revision_cannot_replace_existing_action(self):
        self.ready()
        self.execute()
        revised = copy.deepcopy(self.artifact)
        revised['sources'] = ['revised source notes']
        identifier = runtime.register(self.db, revised)
        validation.validate(self.db, identifier)
        code, output = terminal_approval(self.db, identifier)
        self.assertEqual(code, 0, output)
        self.rejected(lambda: self.execute(identifier=identifier), 409)
        self.assertEqual(self.counts(), {'objects': 1, 'writes': 1})


if __name__ == '__main__':
    unittest.main()
