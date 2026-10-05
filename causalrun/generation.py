"""Package host-agent-written verifier source; this module never calls a model."""
from .contracts import Rejected, check_artifact, implementation_digest
from .discovery import inspect_api, questions


def build_http_contract(contract, source):
    """Bind an agent's declarative HTTP contract to the executing code."""
    if not isinstance(contract, dict):
        raise Rejected('Provide an HTTP contract object', 400)
    artifact = dict(contract, schema_version=4, version=1,
                    operation='http.json.write.v1', implementation=implementation_digest(),
                    verifier={'kind': 'python.receipt.v1', 'source': source})
    check_artifact(artifact)
    return artifact


def build_contract(interview, verifier_source):
    if set(interview) != {'target', 'source', 'operation_id', 'api_version', 'answers'}:
        raise Rejected('Use the completed interview contract', 400)
    api = inspect_api(interview['source'])
    write = next((item for item in api['operations']
                  if item['operation_id'] == interview['operation_id']), None)
    if (write is None or write['method'] != 'POST' or write['path'] != '/values'
            or api['api_version'] != interview['api_version']
            or write['recovery'].get('receipt_path') != '/receipts/{action_id}'
            or write['recovery'].get('correlation') != 'action_id'):
        raise Rejected('Documented operation changed or is not supported by the gate 2 controlled profile', 400)
    authentication = api['authentication']
    if (write['security'] != [{'providerBearer': []}]
            or authentication.get('providerBearer') != {'type': 'http', 'scheme': 'bearer'}):
        raise Rejected('Review unsupported authentication before generating a connector', 400)
    receipt_operation = next((item for item in api['operations']
                              if item['path'] == write['recovery']['receipt_path'] and item['method'] == 'GET'), None)
    if (receipt_operation is None or receipt_operation['security'] != [{'receiptBearer': []}]
            or authentication.get('receiptBearer') != {'type': 'http', 'scheme': 'bearer'}):
        raise Rejected('Review unsupported receipt authentication before generating a connector', 400)
    answers = interview['answers']
    if (answers.get('sandbox') != questions()[1]['options'][0]
            or answers.get('unknown_policy') not in questions()[2]['options']):
        raise Rejected('Sandbox authorization and a blocking uncertainty policy are required', 400)
    artifact = {
        'schema_version': 2, 'name': 'controlled-value', 'version': 1,
        'target': interview['target'], 'operation': 'controlled.value.create.v1',
        'expected': {'value_from': 'payload.value', 'description': answers['expected_behavior']},
        'verifier': {'kind': 'python.receipt.v1', 'source': verifier_source},
        'adapter': {'write_path': write['path'], 'receipt_path': write['recovery']['receipt_path']},
        'authentication': {'type': 'bearer', 'write_secret': 'CAUSALRUN_PROVIDER_TOKEN',
                           'read_secret': 'CAUSALRUN_RECEIPT_TOKEN'},
        'interview': answers,
        'limitations': ['Missing receipt does not prove non-execution'],
        'sources': [interview['source']], 'api_version': api['api_version'],
        'implementation': implementation_digest(),
    }
    check_artifact(artifact)
    return artifact


def build_github_contract(repository, author, source, answers, target='https://api.github.com'):
    """Package host-agent source with the user's explicit observable contract."""
    from .github import LIMITATIONS, VERSION
    artifact = {
        'schema_version': 3, 'name': 'github-issue', 'version': 1,
        'target': target, 'repository': repository, 'author': author,
        'operation': 'github.issue.create.v1', 'api_version': VERSION,
        'expected': {'title_from': 'payload.title', 'body_from': 'payload.body',
                     'description': answers['expected_behavior']},
        'verifier': {'kind': 'python.receipt.v1', 'source': source},
        'adapter': {'kind': 'github.issue.v1', 'page_limit': 10},
        'authentication': {'type': 'bearer', 'write_secret': 'CAUSALRUN_PROVIDER_TOKEN',
                           'read_secret': 'CAUSALRUN_RECEIPT_TOKEN'},
        'interview': answers, 'limitations': LIMITATIONS,
        'sources': ['https://docs.github.com/en/rest/issues/issues',
                    'https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api'],
        'implementation': implementation_digest(),
    }
    check_artifact(artifact)
    return artifact
