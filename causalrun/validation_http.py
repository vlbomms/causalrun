"""Pure fixture checks, not certification of a remote application's guarantees."""
from . import storage
from .contracts import canonical, digest
from .http_json import binding
from .runtime import load_connector, now
from .verifiers import confirms


def validate_http(path, identifier, artifact):
    fixture = artifact['fixture']
    action_id = 'validation-action'
    payload = fixture['payload']
    evidence = binding(fixture['evidence'], action_id, payload)
    source = artifact['verifier']['source']
    scenarios = [
        ('matching_evidence', action_id, payload, evidence, True),
        ('missing_evidence', action_id, payload, None, False),
        ('wrong_action', 'different-action', payload, evidence, False),
        ('wrong_payload', action_id, fixture['different_payload'], evidence, False),
    ]
    cases = [{'name': name, 'passed': confirms(source, action, value, receipt) is expected}
             for name, action, value, receipt, expected in scenarios]
    report = {'connector_digest': identifier, 'checked_at': now(),
              'scope': 'Supplied pure fixtures only; no remote requests or provider guarantee proof',
              'passed': sum(item['passed'] for item in cases),
              'failed': sum(not item['passed'] for item in cases),
              'provider_requests': 0, 'cases': cases}
    with storage.connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        load_connector(db, identifier)
        db.execute('INSERT OR REPLACE INTO validations VALUES(?,?,?)',
                   (identifier, canonical(report), digest(report)))
        db.execute('DELETE FROM approvals WHERE digest=?', (identifier,))
    return report
