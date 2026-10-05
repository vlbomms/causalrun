"""Preflight authority, one dispatch, and durable receipt inspection."""
import json
import uuid
from datetime import datetime, timezone
from . import storage
from .contracts import (Rejected, canonical, check_artifact, check_payload,
                        check_receipt, digest, validation_passed)
from .transport import request


def now():
    return datetime.now(timezone.utc).isoformat()


def event(db, action_id, kind, detail):
    db.execute('INSERT INTO events(action_id,kind,detail,recorded_at) VALUES(?,?,?,?)',
               (action_id, kind, canonical(detail), now()))


def load_connector(db, connector_digest):
    row = db.execute('SELECT artifact FROM connectors WHERE digest=?',
                     (connector_digest,)).fetchone()
    if row is None:
        raise Rejected('Connector not registered', 404)
    artifact = json.loads(row['artifact'])
    check_artifact(artifact)
    if digest(artifact) != connector_digest:
        raise Rejected('Connector changed; validation and approval are invalid')
    return artifact


def register(path, artifact):
    check_artifact(artifact)
    identifier = digest(artifact)
    with storage.connect(path) as db:
        db.execute('INSERT OR IGNORE INTO connectors VALUES(?,?)',
                   (identifier, canonical(artifact)))
    return identifier


def preflight(db, identifier):
    artifact = load_connector(db, identifier)
    validation = db.execute('SELECT * FROM validations WHERE digest=?', (identifier,)).fetchone()
    if validation is None:
        raise Rejected('Validated verifier required before write')
    report = json.loads(validation['report'])
    if (digest(report) != validation['report_digest']
            or not validation_passed(report, identifier, artifact)):
        raise Rejected('Validation record is invalid')
    approval = db.execute('SELECT * FROM approvals WHERE digest=?', (identifier,)).fetchone()
    if approval is None or approval['report_digest'] != validation['report_digest']:
        raise Rejected('Approval of this exact connector and validation is required')
    return artifact


def approve(path, identifier, confirmation, reviewed_report_digest):
    if confirmation != identifier:
        raise Rejected('Approval confirmation must match the exact connector digest')
    with storage.connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        artifact = load_connector(db, identifier)
        validation = db.execute('SELECT * FROM validations WHERE digest=?', (identifier,)).fetchone()
        if validation is None or digest(json.loads(validation['report'])) != validation['report_digest']:
            raise Rejected('An intact validation report is required')
        if validation['report_digest'] != reviewed_report_digest:
            raise Rejected('Validation changed during review; inspect it again')
        report = json.loads(validation['report'])
        if not validation_passed(report, identifier, artifact):
            raise Rejected('Validation did not pass')
        db.execute('INSERT OR REPLACE INTO approvals VALUES(?,?,?)',
                   (identifier, validation['report_digest'], now()))


def result(path, action_id):
    with storage.connect(path) as db:
        row = db.execute('SELECT * FROM actions WHERE id=?', (action_id,)).fetchone()
        if row is None:
            raise Rejected('Action not found', 404)
        events = db.execute('SELECT sequence,kind,detail,recorded_at FROM events WHERE action_id=? ORDER BY sequence',
                            (action_id,)).fetchall()
    return {'id': row['id'], 'connector_digest': row['connector_digest'],
            'action_key': row['action_key'], 'payload': json.loads(row['payload']),
            'state': row['state'], 'receipt': json.loads(row['receipt']) if row['receipt'] else None,
            'events': [dict(item, detail=json.loads(item['detail'])) for item in events]}


def commit_receipt(path, action_id, receipt, kind):
    with storage.connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM actions WHERE id=?', (action_id,)).fetchone()
        artifact = load_connector(db, row['connector_digest'])
        check_receipt(receipt, action_id, json.loads(row['payload']), artifact)
        if row['state'] != 'COMMITTED':
            db.execute("UPDATE actions SET state='COMMITTED',receipt=? WHERE id=?",
                       (canonical(receipt), action_id))
            event(db, action_id, kind, receipt)


def execute(path, identifier, action_key, payload, provider_token):
    if not isinstance(action_key, str) or not action_key.strip() or len(action_key) > 200:
        raise Rejected('A stable action key is required', 400)
    with storage.connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        artifact = preflight(db, identifier)
        check_payload(payload, artifact)
        scope_fields = {'name': artifact['name'], 'target': artifact['target'],
                        'operation': artifact['operation']}
        if artifact['schema_version'] == 3:
            scope_fields['repository'] = artifact['repository']
        scope = digest(scope_fields)
        previous = db.execute('SELECT * FROM actions WHERE action_scope=? AND action_key=?',
                              (scope, action_key)).fetchone()
        if previous:
            if previous['connector_digest'] != identifier:
                raise Rejected('Existing action is bound to a different connector version')
            if previous['payload'] != canonical(payload):
                raise Rejected('Changed payload under an existing action key')
            action_id = previous['id']
        else:
            action_id = str(uuid.uuid4())
            db.execute('INSERT INTO actions VALUES(?,?,?,?,?,?,NULL)',
                       (action_id, scope, identifier, action_key, canonical(payload), 'IN_DOUBT'))
            event(db, action_id, 'AUTHORIZED', {'target': artifact['target']})
    if previous:
        # Even an IN_DOUBT record must not allocate a replacement attempt.
        return result(path, action_id)
    try:
        if artifact['schema_version'] == 3:
            from .github import write
            receipt = write(artifact, action_id, payload, provider_token)
        else:
            status, receipt = request(artifact['target'], '/values', provider_token,
                                      {'action_id': action_id, 'payload': payload})
            if status != 200:
                raise Rejected('Provider did not supply a receipt')
        commit_receipt(path, action_id, receipt, 'RECEIPT_RECORDED')
    except Exception:
        # A transport error, malformed receipt, or failed persistence is uncertain.
        # Never return provider exception text or secrets to the model.
        with storage.connect(path) as db:
            event(db, action_id, 'OUTCOME_UNCONFIRMED', {'reason': 'No durable matching receipt'})
    return result(path, action_id)


def verify(path, action_id, receipt_token):
    action = result(path, action_id)
    if action['state'] == 'COMMITTED':
        return action
    with storage.connect(path) as db:
        artifact = preflight(db, action['connector_digest'])
    try:
        if artifact['schema_version'] == 3:
            from .github import lookup
            receipt = lookup(artifact, action_id, action['payload'], receipt_token)
        else:
            status, receipt = request(artifact['target'], '/receipts/' + action_id, receipt_token, allow_missing=True)
            if status != 200:
                raise Rejected('No conclusive receipt')
        commit_receipt(path, action_id, receipt, 'VERIFIED_SUCCESS')
    except Exception:
        with storage.connect(path) as db:
            event(db, action_id, 'VERIFICATION_UNKNOWN', {'reason': 'No matching authoritative receipt'})
    return result(path, action_id)
