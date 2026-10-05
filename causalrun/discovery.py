"""Read API descriptions for a host agent; interview only for user intent/gaps."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener
from .contracts import Rejected
from .transport import NoRedirect


def read_description(source):
    if source.startswith(('https://', 'http://')):
        url = urlsplit(source)
        if url.username or url.password or url.fragment:
            raise Rejected('Documentation URL must not contain credentials or a fragment', 400)
        opener = build_opener(ProxyHandler({}), NoRedirect())
        with opener.open(Request(source, headers={'Accept': 'application/json, application/xml'}),
                         timeout=5) as response:
            data = response.read(1024 * 1024 + 1)
    else:
        data = Path(source).read_bytes()
    if len(data) > 1024 * 1024:
        raise Rejected('API description exceeds 1 MiB', 400)
    if data.lstrip().startswith(b'<'):
        # WSDL/XML is inspected, never used to execute SOAP operations automatically.
        root = ET.fromstring(data)
        return {'format': 'wsdl', 'operations': [element.attrib['name']
                for element in root.iter() if element.tag.endswith('}operation')
                and 'name' in element.attrib],
                'next_step': 'Host agent must inspect bindings, schemas, authentication, and official docs.'}
    document = json.loads(data)
    if not isinstance(document, dict) or not ('openapi' in document or document.get('swagger') == '2.0'):
        raise Rejected('Use an OpenAPI/Swagger JSON description, WSDL, or official docs through the host agent', 400)
    return document


def resolve(document, value, depth=0):
    if isinstance(value, dict) and '$ref' in value:
        reference = value['$ref']
        if depth >= 16 or not isinstance(reference, str) or not reference.startswith('#/'):
            return {'unresolved_reference': reference}
        found = document
        try:
            for part in reference[2:].split('/'):
                found = found[part.replace('~1', '/').replace('~0', '~')]
        except (KeyError, TypeError):
            return {'unresolved_reference': reference}
        return resolve(document, found, depth + 1)
    return value


def inspect_api(source):
    document = read_description(source)
    if document.get('format') == 'wsdl':
        return document
    schemes = document.get('components', {}).get('securitySchemes', document.get('securityDefinitions', {}))
    operations = []
    for path, item in document.get('paths', {}).items():
        item = resolve(document, item)
        for method, operation in item.items():
            if method.lower() not in ('get', 'post', 'put', 'patch', 'delete'):
                continue
            operation = resolve(document, operation)
            body = resolve(document, operation.get('requestBody', {}))
            schema = body.get('content', {}).get('application/json', {}).get('schema', {})
            if document.get('swagger') == '2.0':
                parameters = [resolve(document, value) for value in operation.get('parameters', [])]
                schema = next((value.get('schema', {}) for value in parameters if value.get('in') == 'body'), {})
            operations.append({
                'operation_id': operation.get('operationId', method + ':' + path),
                'method': method.upper(), 'path': path,
                'description': operation.get('description', operation.get('summary', '')),
                'request_schema': resolve(document, schema),
                'responses': {code: resolve(document, response)
                              for code, response in operation.get('responses', {}).items()},
                'security': operation.get('security', document.get('security', [])),
                'recovery': operation.get('x-causalrun-recovery', {}),
            })
    return {'format': 'openapi', 'api_version': document.get('info', {}).get('version', ''),
            'authentication': schemes, 'operations': operations}


def questions():
    return [
        {'id': 'expected_behavior', 'title': 'What observable result should count as success?',
         'options': ['The returned value must exactly match payload.value', 'Describe another requirement'],
         'free_text': True},
        {'id': 'sandbox', 'title': 'May validation write to a disposable controlled fixture?',
         'options': ['Yes, only the disposable fixture', 'No; stop before any test writes'],
         'free_text': True},
        {'id': 'unknown_policy', 'title': 'If evidence is inconclusive, what should the agent do?',
         'options': ['Keep blocked and request review', 'Keep blocked and check again later'],
         'free_text': True},
    ]


def interview(source, target, ask=input, tell=print):
    api = inspect_api(source)
    if api['format'] != 'openapi':
        raise Rejected('The host agent must interpret this description before preparing a connector', 400)
    write = next((item for item in api['operations'] if item['operation_id'] == 'createValue'), None)
    if write is None:
        raise Rejected('Gate 2 automated preparation supports the controlled createValue operation only', 400)
    tell('Documented operation: ' + write['method'] + ' ' + write['path'])
    tell('Documented authentication: ' + json.dumps(write['security']))
    tell('Known API facts are not questions. Do not paste credentials into the interview.')
    answers = {}
    for question in questions():
        tell(question['title'])
        for number, option in enumerate(question['options'], start=1):
            tell(str(number) + '. ' + option)
        answer = ask('Choose a number or enter your own answer: ').strip()
        if answer in ('1', '2'):
            answer = question['options'][int(answer) - 1]
        if not answer or len(answer) > 1000:
            raise Rejected('A concise answer is required', 400)
        answers[question['id']] = answer
    if answers['sandbox'] != questions()[1]['options'][0]:
        raise Rejected('No authorized fixture: stop without test writes', 400)
    if answers['unknown_policy'] not in questions()[2]['options']:
        raise Rejected('Recovery must keep uncertain actions blocked; clarify your policy', 400)
    return {'target': target, 'source': source, 'operation_id': write['operation_id'],
            'api_version': api['api_version'], 'answers': answers}
