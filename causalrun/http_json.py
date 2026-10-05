"""Approved JSON requests and pure evidence checks; no generated network code."""
import json
import os
import re
import time
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, build_opener, ProxyHandler
from .contracts import Rejected, canonical
from .transport import NoRedirect

METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}
HEADER = re.compile(r'^[A-Za-z][A-Za-z0-9-]{0,63}$')
SECRET = re.compile(r'^[A-Z][A-Z0-9_]{0,99}$')
FORBIDDEN_HEADERS = {'authorization', 'host', 'cookie', 'proxy-authorization',
                     'content-length', 'transfer-encoding', 'connection'}
CASE_NAMES = {'matching_evidence', 'missing_evidence', 'wrong_action', 'wrong_payload'}


def binding(value, action_id, payload):
    if isinstance(value, dict):
        if '$text' in value:
            if set(value) != {'$text'} or not isinstance(value['$text'], list) or len(value['$text']) > 32:
                raise Rejected('Text template requires at most 32 parts', 400)
            parts = [binding(part, action_id, payload) for part in value['$text']]
            if not all(isinstance(part, str) for part in parts):
                raise Rejected('Text template parts must be strings', 400)
            return ''.join(parts)
        if '$bind' in value:
            if value == {'$bind': 'action_id'}:
                return action_id
            if set(value) == {'$bind', 'path'} and value['$bind'] == 'payload':
                path = value['path']
                if not isinstance(path, list) or not path or not all(isinstance(k, str) for k in path):
                    raise Rejected('Payload binding needs a non-empty field path', 400)
                found = payload
                for key in path:
                    if not isinstance(found, dict) or key not in found:
                        raise Rejected('Payload binding field is missing', 400)
                    found = found[key]
                return found
            raise Rejected('Unsupported JSON binding', 400)
        return {k: binding(v, action_id, payload) for k, v in value.items()}
    if isinstance(value, list):
        return [binding(v, action_id, payload) for v in value]
    return value


def scalar(value):
    if not isinstance(value, (str, int, float, bool)) or len(str(value)) > 4096:
        raise Rejected('Path and query bindings must be short scalar values', 400)
    return str(value)


def route(spec, action_id, payload):
    parts = [scalar(binding(part, action_id, payload)) for part in spec['path']]
    if any(not part or part in ('.', '..') or '\\' in part for part in parts):
        raise Rejected('Empty and relative path segments are forbidden', 400)
    path = '/' + '/'.join(quote(part, safe='') for part in parts)
    query = [(key, scalar(binding(value, action_id, payload))) for key, value in spec['query'].items()]
    return path + ('?' + urlencode(query) if query else '')


def check_request(spec, write, sample):
    required = {'method', 'path', 'query', 'headers', 'statuses'} | ({'body'} if write else set())
    if not write and isinstance(spec, dict) and 'pagination' in spec:
        required.add('pagination')
    if not isinstance(spec, dict) or set(spec) != required:
        raise Rejected('HTTP request requires exactly the documented fields', 400)
    if spec['method'] not in (METHODS if write else {'GET'}):
        raise Rejected('Evidence requests must be GET; writes must use a mutation method', 400)
    if not isinstance(spec['path'], list) or not 1 <= len(spec['path']) <= 32:
        raise Rejected('Request path requires 1 to 32 segments', 400)
    if not isinstance(spec['query'], dict) or len(spec['query']) > 32:
        raise Rejected('Request query must be a small object', 400)
    if not all(isinstance(k, str) and len(k) <= 100 for k in spec['query']):
        raise Rejected('Invalid query name', 400)
    if (not isinstance(spec['statuses'], list) or not spec['statuses']
            or not all(type(s) is int and 200 <= s <= 299 for s in spec['statuses'])):
        raise Rejected('Expected statuses must be successful HTTP status codes', 400)
    headers = spec['headers']
    if not isinstance(headers, dict) or len(headers) > 16:
        raise Rejected('Headers must be a small object', 400)
    for key, value in headers.items():
        if (not isinstance(key, str) or not HEADER.fullmatch(key)
                or key.lower() in FORBIDDEN_HEADERS or not isinstance(value, str)
                or len(value) > 1024 or any(ord(c) < 32 or ord(c) == 127 for c in value)):
            raise Rejected('Unsafe HTTP header', 400)
    route(spec, 'validation-action', sample)
    if not write and 'pagination' in spec:
        policy = spec['pagination']
        if (not isinstance(policy, dict) or set(policy) != {'page', 'size', 'page_size', 'limit'}
                or not all(isinstance(policy[k], str) and 1 <= len(policy[k]) <= 100
                           and all(ord(c) >= 32 and ord(c) != 127 for c in policy[k]) for k in ('page', 'size'))
                or policy['page'] == policy['size']
                or type(policy['page_size']) is not int or not 1 <= policy['page_size'] <= 100
                or type(policy['limit']) is not int or not 1 <= policy['limit'] <= 10
                or policy['page'] in spec['query'] or policy['size'] in spec['query']):
            raise Rejected('Invalid bounded page-number pagination', 400)
    if write:
        canonical(binding(spec['body'], 'validation-action', sample))


def check_metadata(artifact):
    try:
        target = urlsplit(artifact['target'])
        valid_port = target.port
    except (ValueError, TypeError):
        raise Rejected('Invalid API origin', 400) from None
    if (not target.hostname or any(ord(c) <= 32 or ord(c) == 127 for c in artifact['target'])
            or target.username or target.password or target.path
            or target.query or target.fragment or target.scheme not in ('https', 'http')
            or (target.scheme == 'http' and (target.hostname != '127.0.0.1' or not valid_port))):
        raise Rejected('Use an exact HTTPS origin or loopback HTTP origin', 400)
    if artifact['operation'] != 'http.json.write.v1':
        raise Rejected('Unsupported generic HTTP operation', 400)
    if not isinstance(artifact['api_version'], str) or not artifact['api_version'].strip():
        raise Rejected('API version is required', 400)
    if not isinstance(artifact['expected'], str) or not artifact['expected'].strip():
        raise Rejected('Expected application behavior is required', 400)
    limitations = artifact['limitations']
    if (not isinstance(limitations, list) or not all(isinstance(item, str) and item.strip() for item in limitations)
            or not {'Missing evidence does not prove non-execution',
                    'Fixture checks do not prove provider guarantees'} <= set(limitations)):
        raise Rejected('Generic recovery limitations must be explicit', 400)
    fixture = artifact['fixture']
    if not isinstance(fixture, dict) or set(fixture) != {'payload', 'evidence', 'different_payload'}:
        raise Rejected('Positive evidence and a different payload are required', 400)
    if not isinstance(fixture['payload'], dict) or not isinstance(fixture['different_payload'], dict):
        raise Rejected('Fixture payloads must be JSON objects', 400)
    if fixture['payload'] == fixture['different_payload']:
        raise Rejected('Negative fixture payload must differ', 400)
    binding(fixture['evidence'], 'validation-action', fixture['payload'])
    adapter = artifact['adapter']
    if not isinstance(adapter, dict) or set(adapter) != {'write', 'read'}:
        raise Rejected('Declare exactly one write and one evidence read', 400)
    check_request(adapter['write'], True, fixture['payload'])
    check_request(adapter['read'], False, fixture['payload'])
    auth = artifact['authentication']
    if not isinstance(auth, dict) or set(auth) != {'write', 'read'}:
        raise Rejected('Declare separate write and read authentication', 400)
    for policy in auth.values():
        if policy == {'type': 'none'}:
            continue
        if (not isinstance(policy, dict) or policy.get('type') not in ('bearer', 'api_key')
                or set(policy) != ({'type', 'secret'} if policy['type'] == 'bearer' else {'type', 'secret', 'header'})
                or not isinstance(policy['secret'], str) or not SECRET.fullmatch(policy['secret'])):
            raise Rejected('Authentication requires an environment secret reference', 400)
        if policy['type'] == 'api_key':
            name = policy['header']
            if (not isinstance(name, str) or not HEADER.fullmatch(name)
                    or name.lower() in FORBIDDEN_HEADERS | {'content-type'}):
                raise Rejected('Unsafe API-key header', 400)
    if (not isinstance(artifact['verifier'], dict)
            or artifact['verifier'].get('kind') != 'python.receipt.v1'
            or set(artifact['verifier']) != {'kind', 'source'}):
        raise Rejected('A pure generated verifier is required', 400)
    from .verifiers import compile_verifier
    compile_verifier(artifact['verifier']['source'])
    text = canonical(artifact)
    for policy in auth.values():
        secret = os.environ.get(policy.get('secret', ''))
        if secret and secret in text:
            raise Rejected('Use secret references, not credential values, in the contract', 400)


def credentials(policy):
    if policy['type'] == 'none':
        return {}
    token = os.environ.get(policy['secret'])
    if not token or len(token) > 8192 or any(ord(c) < 32 or ord(c) == 127 for c in token):
        raise Rejected('Configured API credential is missing or invalid', 400)
    if policy['type'] == 'bearer':
        return {'Authorization': 'Bearer ' + token}
    return {policy['header']: token}


def prepare_request(artifact, kind, action_id, payload, page=None):
    spec = artifact['adapter'][kind]
    path = route(spec, action_id, payload)
    if page is not None:
        policy = spec['pagination']
        path += ('&' if spec['query'] else '?') + urlencode({policy['page']: page, policy['size']: policy['page_size']})
    url = artifact['target'] + path
    body = binding(spec['body'], action_id, payload) if kind == 'write' else None
    data = canonical(body).encode() if kind == 'write' else None
    if data is not None and len(data) > 65536:
        raise Rejected('Write body exceeds 64 KiB', 400)
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    headers.update(spec['headers'])
    # Authentication wins over static headers, regardless of header casing.
    auth = credentials(artifact['authentication'][kind])
    for key in auth:
        headers = {k: v for k, v in headers.items() if k.lower() != key.lower()}
    headers.update(auth)
    return Request(url, data=data, headers=headers, method=spec['method'])


def request_json(artifact, kind, action_id, payload, page=None, deadline=None):
    request = prepare_request(artifact, kind, action_id, payload, page)
    opener = build_opener(ProxyHandler({}), NoRedirect())
    deadline = deadline or time.monotonic() + 10
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise Rejected('Evidence deadline reached')
    with opener.open(request, timeout=min(5, remaining)) as response:
        if response.status not in artifact['adapter'][kind]['statuses']:
            raise Rejected('Provider returned an unexpected status')
        data = bytearray()
        while True:
            if time.monotonic() >= deadline:
                raise Rejected('Evidence deadline reached')
            chunk = response.read1(min(8192, 65537 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > 65536:
                raise Rejected('Provider evidence exceeds 64 KiB')
        # Do not persist reflected request credentials in an application receipt.
        value = json.loads(data.decode('utf-8'))
        text = canonical(value)
        for policy in artifact['authentication'].values():
            secret = os.environ.get(policy.get('secret', ''))
            if secret and secret in text:
                raise Rejected('Provider evidence contains a configured credential')
        return value


def call(artifact, kind, action_id, payload):
    policy = artifact['adapter'][kind].get('pagination')
    if policy is None:
        return request_json(artifact, kind, action_id, payload)
    evidence = []
    deadline = time.monotonic() + 15
    for page in range(1, policy['limit'] + 1):
        items = request_json(artifact, kind, action_id, payload, page, deadline)
        if not isinstance(items, list) or len(items) > policy['page_size']:
            raise Rejected('Paginated evidence must be a bounded JSON list')
        evidence.extend(items)
        if len(canonical(evidence).encode()) > 65536:
            raise Rejected('Combined evidence exceeds 64 KiB')
        if len(items) < policy['page_size']:
            return evidence
    raise Rejected('Evidence page limit reached; completeness is unknown')
