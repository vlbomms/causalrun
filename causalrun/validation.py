"""Validate the fixed receipt contract in a disposable controlled sandbox."""
import json
import secrets
import sqlite3
import tempfile
import threading
import uuid
from pathlib import Path
from examples.provider import create_server
from . import storage
from .contracts import Rejected, canonical, check_receipt, digest
from .runtime import load_connector, now
from .transport import request


def validate(path, identifier):
    with storage.connect(path) as db:
        artifact = load_connector(db, identifier)
    if artifact['schema_version'] == 3:
        from .validation_github import validate_github
        return validate_github(path, identifier, artifact)
    if artifact['schema_version'] == 2:
        from .validation_generated import validate_generated
        return validate_generated(path, identifier, artifact)
    cases = []
    with tempfile.TemporaryDirectory() as directory:
        provider_db = str(Path(directory) / 'provider.sqlite')
        token = secrets.token_hex(24)
        server = create_server(provider_db, 0, token)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        target = 'http://127.0.0.1:' + str(server.server_port)
        action_id = str(uuid.uuid4())
        payload = {'value': 'validation value'}
        try:
            status, receipt = request(target, '/receipts/' + action_id, token, allow_missing=True)
            assert status == 404 and receipt is None
            cases.append({'name': 'missing_receipt_is_unknown', 'passed': True})
            status, receipt = request(target, '/values', token,
                                      {'action_id': action_id, 'payload': payload})
            assert status == 200
            check_receipt(receipt, action_id, payload)
            status, found = request(target, '/receipts/' + action_id, token, allow_missing=True)
            assert status == 200 and found == receipt
            # Inspect independent application state, not just the runtime success predicate.
            with sqlite3.connect(provider_db) as db:
                assert db.execute('SELECT value FROM values_and_receipts WHERE action_id=?',
                                  (action_id,)).fetchone() == ('validation value',)
            cases.append({'name': 'atomic_write_and_matching_receipt', 'passed': True})
            status, repeated = request(target, '/values', token,
                                         {'action_id': action_id, 'payload': payload})
            assert status == 200 and repeated == receipt
            with sqlite3.connect(provider_db) as db:
                assert db.execute('SELECT count(*) FROM values_and_receipts').fetchone()[0] == 1
                assert db.execute('SELECT count(*) FROM requests').fetchone()[0] == 2
            cases.append({'name': 'controlled_idempotent_repeat', 'passed': True})
            try:
                check_receipt(receipt, action_id, {'value': 'different'})
            except Rejected:
                cases.append({'name': 'conflicting_receipt_rejected', 'passed': True})
            else:
                raise AssertionError('A wrong receipt passed validation')
        except Exception:
            cases.append({'name': 'validation_failure', 'passed': False})
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=5)
    report = {'connector_digest': identifier, 'checked_at': now(),
              'scope': 'Fixed controlled receipt implementation in a disposable sandbox; '
                       'not generated verifier validation or proof of arbitrary target behavior',
              'passed': sum(item['passed'] for item in cases),
              'failed': sum(not item['passed'] for item in cases),
              'provider_objects': 1 if len(cases) >= 3 else None,
              'provider_requests': 2 if len(cases) >= 3 else None,
              'cases': cases}
    with storage.connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        load_connector(db, identifier)
        db.execute('INSERT OR REPLACE INTO validations VALUES(?,?,?)',
                   (identifier, canonical(report), digest(report)))
        # A fresh report, even for the same artifact, needs explicit approval.
        db.execute('DELETE FROM approvals WHERE digest=?', (identifier,))
    return report
