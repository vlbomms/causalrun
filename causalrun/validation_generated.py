"""Exercise generated source against controlled faults and an independent SQL oracle."""
import copy
import secrets
import sqlite3
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from examples.provider import create_server
from . import storage
from .contracts import canonical, digest
from .runtime import load_connector, now
from .transport import request
from .verifiers import confirms


def validate_generated(path, identifier, artifact):
    cases = []
    token, read_token = secrets.token_hex(24), secrets.token_hex(24)
    with tempfile.TemporaryDirectory() as directory:
        provider_db = str(Path(directory) / 'provider.sqlite')
        server = create_server(provider_db, 0, token, receipt_token=read_token)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        target = 'http://127.0.0.1:' + str(server.server_port)
        payload = {'value': 'validation value'}
        identifier_one = str(uuid.uuid4())

        def verify(evidence, action_id=identifier_one):
            return confirms(artifact['verifier']['source'], action_id, payload, evidence)

        def check(name, expected, evidence):
            found = verify(evidence)
            cases.append({'name': name, 'passed': found == expected,
                          'expected_confirmation': expected, 'actual_confirmation': found})

        def fetch(action_id):
            status, evidence = request(target, '/receipts/' + action_id, read_token, allow_missing=True)
            return evidence if status == 200 else None

        def oracle_count():
            with sqlite3.connect(provider_db) as db:
                return {'objects': db.execute('SELECT count(*) FROM values_and_receipts').fetchone()[0],
                        'writes': db.execute('SELECT count(*) FROM requests').fetchone()[0]}

        try:
            status, receipt = request(target, '/values', token,
                                      {'action_id': identifier_one, 'payload': payload})
            with sqlite3.connect(provider_db) as db:
                actual = db.execute('SELECT value FROM values_and_receipts WHERE action_id=?',
                                    (identifier_one,)).fetchone()
            check('matching_receipt', True, receipt)
            cases[-1]['oracle_matched'] = status == 200 and actual == ('validation value',)
            cases[-1]['passed'] = cases[-1]['passed'] and cases[-1]['oracle_matched']
            check('missing_receipt', False, None)
            check('malformed_receipt', False, 'not a receipt')
            for mode in ('wrong_action', 'wrong_payload', 'wrong_value'):
                server.fault_mode = mode
                check(mode, False, fetch(identifier_one))
            server.fault_mode = 'none'
            partial = copy.deepcopy(receipt)
            partial.pop('result')
            check('partial_receipt', False, partial)

            lost_id = str(uuid.uuid4())
            server.fault_mode = 'drop_response'
            lost = False
            try:
                request(target, '/values', token, {'action_id': lost_id, 'payload': payload})
            except Exception:
                lost = True
            server.fault_mode = 'none'
            with sqlite3.connect(provider_db) as db:
                committed = db.execute('SELECT value FROM values_and_receipts WHERE action_id=?',
                                       (lost_id,)).fetchone()
            found = fetch(lost_id)
            cases.append({'name': 'lost_response', 'passed': lost and committed == ('validation value',)
                          and verify(found, lost_id), 'schedule': 'provider commit, disconnect response, GET receipt'})

            delayed_id = str(uuid.uuid4())
            server.fault_mode = 'delay_commit'
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(request, target, '/values', token,
                                      {'action_id': delayed_id, 'payload': payload})
                received = server.request_received.wait(timeout=5)
                before = fetch(delayed_id)
                with sqlite3.connect(provider_db) as db:
                    absent = db.execute('SELECT count(*) FROM values_and_receipts WHERE action_id=?',
                                        (delayed_id,)).fetchone()[0] == 0
                confirmed_before = verify(before, delayed_id)
                unknown_before = not confirmed_before
                server.allow_commit.set()
                pending.result(timeout=5)
                server.fault_mode = 'none'
                after = fetch(delayed_id)
                cases.append({'name': 'delayed_commit', 'passed': received and absent and unknown_before
                              and verify(after, delayed_id), 'confirmed_before_commit': confirmed_before, 'schedule': 'hold POST before transaction, '
                              'GET missing receipt, release commit, GET matching receipt'})

            server.fault_mode = 'verifier_error'
            unavailable = False
            try:
                fetch(identifier_one)
            except Exception:
                unavailable = True
            cases.append({'name': 'verifier_unavailable', 'passed': unavailable and not verify(None),
                          'actual_confirmation': verify(None), 'schedule': 'receipt GET returns 503; no conclusion'})
            counts = oracle_count()
        except Exception:
            cases.append({'name': 'validation_error', 'passed': False})
            counts = oracle_count()
        finally:
            server.allow_commit.set()
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    report = {'connector_digest': identifier, 'checked_at': now(),
              'scope': 'Generated pure verifier; controlled fixture only, not a general API guarantee',
              'passed': sum(case['passed'] for case in cases),
              'failed': sum(not case['passed'] for case in cases),
              'provider_objects': counts['objects'], 'provider_requests': counts['writes'],
              'false_successes': sum(case.get('expected_confirmation') is False
                                     and case.get('actual_confirmation') is True for case in cases)
                                 + sum(case.get('confirmed_before_commit') is True for case in cases)
                                 + sum(case['name'] == 'verifier_unavailable' and case.get('actual_confirmation') is True
                                       for case in cases),
              'false_failures': 0, 'failure_conclusions_supported': False, 'cases': cases}
    with storage.connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        load_connector(db, identifier)
        db.execute('INSERT OR REPLACE INTO validations VALUES(?,?,?)',
                   (identifier, canonical(report), digest(report)))
        db.execute('DELETE FROM approvals WHERE digest=?', (identifier,))
    return report
