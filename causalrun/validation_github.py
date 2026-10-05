"""Exercise the stored verifier and adapter against a disposable HTTP provider."""
import copy
import threading
from examples.github_provider import create_server
from . import github, storage
from .contracts import Rejected, canonical, check_receipt, digest
from .runtime import load_connector, now
from .verifiers import confirms


def validate_github(path, identifier, artifact):
    server = create_server(artifact['repository'], artifact['author'])
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    fixture = dict(artifact, target=server.target)
    payload = {'title': 'Validation issue', 'body': 'Expected body'}
    cases = []
    source = artifact['verifier']['source']

    def evaluate(name, setup, positive=False):
        server.denied = server.untrusted_link = False
        server.issues = copy.deepcopy(baseline)
        setup()
        try:
            evidence = github.lookup(fixture, 'validation-action', payload, 'fixture-read')
        except Exception:
            evidence = None
        confirmed = confirms(source, 'validation-action', payload, evidence)
        passed = confirmed == positive
        if positive and evidence is not None:
            # Independent fixture fields, rather than the generated predicate, are the oracle.
            passed = passed and evidence['result']['number'] == 1 and server.issues[-1]['title'] == payload['title']
        cases.append({'name': name, 'passed': passed, 'conclusion': 'COMMITTED' if confirmed else 'UNKNOWN'})

    try:
        receipt = github.write(fixture, 'validation-action', payload, 'fixture-write')
        check_receipt(receipt, 'validation-action', payload, artifact)
        baseline = copy.deepcopy(server.issues)
        evaluate('matching_issue', lambda: None, True)
        # The fixture commits the second POST before dropping its HTTP response.
        server.drop_response = True
        lost_payload = {'title': 'Lost response', 'body': 'Persisted before disconnect'}
        try:
            github.write(fixture, 'lost-action', lost_payload, 'fixture-write')
            lost = False
        except Exception:
            lost = True
        server.drop_response = False
        evidence = github.lookup(fixture, 'lost-action', lost_payload, 'fixture-read')
        cases.append({'name': 'lost_response', 'passed': lost and server.posts == 2 and
                      confirms(source, 'lost-action', lost_payload, evidence), 'provider_posts': server.posts})

        def paginate():
            unrelated = []
            for number in range(2, 102):
                item = copy.deepcopy(baseline[0])
                item.update(id=number, number=number, body='Unrelated')
                unrelated.append(item)
            server.issues = unrelated + copy.deepcopy(baseline)
        evaluate('pagination', paginate, True)
        def conflict():
            duplicate = copy.deepcopy(baseline[0]); duplicate.update(id=200, number=200)
            server.issues.append(duplicate)
        evaluate('conflicting_markers', conflict)
        evaluate('permission_failure', lambda: setattr(server, 'denied', True))
        evaluate('missing_issue', lambda: setattr(server, 'issues', []))
        evaluate('deleted_issue', lambda: setattr(server, 'issues', []))
        evaluate('altered_marker', lambda: server.issues[0].update(body=payload['body']))
        evaluate('wrong_author', lambda: server.issues[0].update(user={'login': 'other'}))
        evaluate('wrong_fields', lambda: server.issues[0].update(title='Different'))
        evaluate('untrusted_next_page', lambda: setattr(server, 'untrusted_link', True))
    except Exception as error:
        cases.append({'name': 'validation_error', 'passed': False, 'error_type': type(error).__name__})
    finally:
        server.shutdown(); server.server_close(); worker.join(timeout=5)
    report = {'connector_digest': identifier, 'checked_at': now(),
              'scope': 'Controlled GitHub-shaped HTTP fixture; live provider guarantees require separate evidence',
              'passed': sum(c['passed'] for c in cases), 'failed': sum(not c['passed'] for c in cases),
              'provider_posts': server.posts, 'provider_reads': server.reads, 'cases': cases}
    with storage.connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        load_connector(db, identifier)
        db.execute('INSERT OR REPLACE INTO validations VALUES(?,?,?)', (identifier, canonical(report), digest(report)))
        db.execute('DELETE FROM approvals WHERE digest=?', (identifier,))
    return report
