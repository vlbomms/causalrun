"""Gate 1 supports one explicit, inspectable connector and receipt verifier."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit


class Rejected(Exception):
    def __init__(self, message, status=409):
        super().__init__(message)
        self.status = status


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def implementation_digest():
    # Bind approval to the code interpreting the artifact, not just its labels.
    directory = Path(__file__).parent
    sources = {name: (directory / name).read_text()
               for name in ('contracts.py', 'runtime.py', 'transport.py',
                            'validation.py', 'storage.py', 'server.py', '__main__.py',
                            'discovery.py', 'generation.py', 'verifiers.py', 'validation_generated.py', 'github.py', 'validation_github.py', 'native.py', 'installer.py', 'mcp.py', 'http_json.py', 'validation_http.py')}
    sources['examples/provider.py'] = (directory.parent / 'examples/provider.py').read_text()
    sources['examples/openapi.json'] = (directory.parent / 'examples/openapi.json').read_text()
    sources['adapters/opencode/plugin.mjs'] = (directory.parent / 'adapters/opencode/plugin.mjs').read_text()
    sources['examples/github_provider.py'] = (directory.parent / 'examples/github_provider.py').read_text()
    return digest(sources)


def check_artifact(artifact):
    required = {'schema_version', 'name', 'version', 'target', 'operation',
                'expected', 'verifier', 'limitations', 'sources', 'implementation'}
    if isinstance(artifact, dict) and artifact.get('schema_version') in (2, 3):
        required |= {'adapter', 'authentication', 'interview', 'api_version'}
    if isinstance(artifact, dict) and artifact.get('schema_version') == 3:
        required |= {'repository', 'author'}
    if isinstance(artifact, dict) and artifact.get('schema_version') == 4:
        required |= {'adapter', 'authentication', 'api_version', 'fixture'}
    if not isinstance(artifact, dict) or set(artifact) != required:
        raise Rejected('Connector requires exactly the documented fields', 400)
    if artifact['schema_version'] not in (1, 2, 3, 4) or artifact['version'] != 1:
        raise Rejected('Unsupported contract version', 400)
    if not isinstance(artifact['name'], str) or not artifact['name'].strip():
        raise Rejected('Connector name required', 400)
    if artifact['schema_version'] == 4:
        from .http_json import check_metadata
        check_metadata(artifact)
        if not isinstance(artifact['sources'], list) or not artifact['sources']:
            raise Rejected('Evidence sources required', 400)
        if artifact['implementation'] != implementation_digest():
            raise Rejected('Implementation changed; regenerate, validate, and approve')
        canonical(artifact)
        return
    if artifact['schema_version'] == 3:
        check_github_artifact(artifact)
        return
    url = urlsplit(artifact['target'])
    if (url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port
            or url.username or url.password or url.path or url.query or url.fragment):
        raise Rejected('Gate 1 targets must be http://127.0.0.1:PORT', 400)
    if artifact['operation'] != 'controlled.value.create.v1':
        raise Rejected('Unsupported write operation', 400)
    if artifact['schema_version'] == 1:
        if artifact['expected'] != {'value_from': 'payload.value'}:
            raise Rejected('Unsupported expected behavior', 400)
        if artifact['verifier'] != {'kind': 'controlled.receipt.v1'}:
            raise Rejected('A supported verifier is required before any write', 400)
    else:
        expected = artifact['expected']
        if (not isinstance(expected, dict) or set(expected) != {'value_from', 'description'}
                or expected['value_from'] != 'payload.value'
                or not isinstance(expected['description'], str) or not expected['description'].strip()):
            raise Rejected('Expected behavior requires a precise value predicate and description', 400)
        verifier = artifact['verifier']
        if not isinstance(verifier, dict) or set(verifier) != {'kind', 'source'} or verifier['kind'] != 'python.receipt.v1':
            raise Rejected('Generated verifier source is required', 400)
        from .verifiers import compile_verifier
        compile_verifier(verifier['source'])
        if artifact['adapter'] != {'write_path': '/values', 'receipt_path': '/receipts/{action_id}'}:
            raise Rejected('Unsupported controlled adapter routes', 400)
        if artifact['authentication'] != {'type': 'bearer', 'write_secret': 'CAUSALRUN_PROVIDER_TOKEN',
                                           'read_secret': 'CAUSALRUN_RECEIPT_TOKEN'}:
            raise Rejected('Use distinct server-owned write and receipt credentials', 400)
        interview = artifact['interview']
        from .discovery import questions
        if (not isinstance(interview, dict) or set(interview) != {'expected_behavior', 'sandbox', 'unknown_policy'}
                or interview['expected_behavior'] != expected['description']
                or interview['sandbox'] != questions()[1]['options'][0]
                or interview['unknown_policy'] not in questions()[2]['options']):
            raise Rejected('Approved interview policy must authorize only the fixture and block uncertainty', 400)
    if artifact['limitations'] != ['Missing receipt does not prove non-execution']:
        raise Rejected('Recovery limitation must be explicit', 400)
    if not isinstance(artifact['sources'], list) or not artifact['sources']:
        raise Rejected('Evidence sources required', 400)
    if artifact['implementation'] != implementation_digest():
        raise Rejected('Implementation changed; regenerate, validate, and approve')
    canonical(artifact)


def check_payload(payload, artifact=None):
    if artifact is not None and artifact['schema_version'] == 4:
        if not isinstance(payload, dict) or len(canonical(payload).encode()) > 65536:
            raise Rejected('Generic payload must be a JSON object at most 64 KiB', 400)
        from .http_json import route, binding
        for kind in ('write', 'read'):
            route(artifact['adapter'][kind], 'preflight-action', payload)
        binding(artifact['adapter']['write']['body'], 'preflight-action', payload)
        return
    if artifact is not None and artifact['schema_version'] == 3:
        from .github import check_payload as check_issue_payload
        return check_issue_payload(payload)
    if (not isinstance(payload, dict) or set(payload) != {'value'}
            or not isinstance(payload['value'], str) or len(payload['value']) > 4096):
        raise Rejected('Payload must contain only a string value (maximum 4096 characters)', 400)


def check_receipt(receipt, action_id, payload, artifact=None):
    if artifact is not None and artifact['schema_version'] in (2, 3, 4):
        from .verifiers import confirms
        if not confirms(artifact['verifier']['source'], action_id, payload, receipt):
            raise Rejected('Generated verifier could not confirm the expected result')
        return receipt
    if not isinstance(receipt, dict) or receipt != {
            'action_id': action_id, 'payload_digest': digest(payload),
            'result': {'value': payload['value']}}:
        raise Rejected('Receipt does not match this action and expected result')
    return receipt


def example_artifact(target):
    return {
        'schema_version': 1, 'name': 'controlled-value', 'version': 1,
        'target': target, 'operation': 'controlled.value.create.v1',
        'expected': {'value_from': 'payload.value'},
        'verifier': {'kind': 'controlled.receipt.v1'},
        'limitations': ['Missing receipt does not prove non-execution'],
        'sources': ['examples/provider.py: atomic value and receipt transaction'],
        'implementation': implementation_digest(),
    }


def validation_case_names(artifact):
    if artifact['schema_version'] == 4:
        from .http_json import CASE_NAMES
        return CASE_NAMES
    if artifact['schema_version'] == 3:
        from .github import CASE_NAMES
        return CASE_NAMES
    if artifact['schema_version'] == 1:
        return {'missing_receipt_is_unknown', 'atomic_write_and_matching_receipt',
                'controlled_idempotent_repeat', 'conflicting_receipt_rejected'}
    return {'matching_receipt', 'missing_receipt', 'malformed_receipt', 'wrong_action',
            'wrong_payload', 'wrong_value', 'partial_receipt', 'lost_response',
            'delayed_commit', 'verifier_unavailable'}


def validation_passed(report, identifier, artifact):
    cases = report.get('cases', [])
    expected = validation_case_names(artifact)
    return (report.get('connector_digest') == identifier and report.get('failed') == 0
            and report.get('passed') == len(expected) and len(cases) == len(expected)
            and {case.get('name') for case in cases} == expected
            and all(case.get('passed') is True for case in cases))


def check_github_artifact(artifact):
    from .github import check_metadata
    from .verifiers import compile_verifier
    if artifact['operation'] != 'github.issue.create.v1':
        raise Rejected('Unsupported GitHub operation', 400)
    check_metadata(artifact)
    verifier = artifact['verifier']
    if (not isinstance(verifier, dict) or set(verifier) != {'kind', 'source'}
            or verifier['kind'] != 'python.receipt.v1'):
        raise Rejected('Generated verifier source is required', 400)
    compile_verifier(verifier['source'])
    if artifact['authentication'] != {'type': 'bearer', 'write_secret': 'CAUSALRUN_PROVIDER_TOKEN',
                                       'read_secret': 'CAUSALRUN_RECEIPT_TOKEN'}:
        raise Rejected('Use server-owned GitHub credentials', 400)
    if not isinstance(artifact['sources'], list) or not artifact['sources']:
        raise Rejected('Evidence sources required', 400)
    if artifact['implementation'] != implementation_digest():
        raise Rejected('Implementation changed; regenerate, validate, and approve')
    canonical(artifact)
