"""GitHub issue creation: one POST; marker-based positive evidence under explicit limits."""
import re
from urllib.parse import parse_qs, urlsplit
from .contracts import Rejected, digest
from .transport import request_with_headers

VERSION = '2026-03-10'
LIMITATIONS = [
    'Missing issue does not prove non-execution',
    'Marker correlation assumes no copying or editing by the approved author during recovery',
    'Pagination is bounded and not a snapshot; incomplete or conflicting evidence stays unknown',
]
HEADERS = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': VERSION}
CASE_NAMES = {'matching_issue', 'lost_response', 'pagination', 'conflicting_markers',
              'permission_failure', 'missing_issue', 'altered_marker', 'deleted_issue',
              'wrong_author', 'wrong_fields', 'untrusted_next_page'}


def check_metadata(artifact):
    target = urlsplit(artifact['target'])
    live = artifact['target'] == 'https://api.github.com'
    fixture = (target.scheme == 'http' and target.hostname == '127.0.0.1' and target.port
               and not target.username and not target.password and not target.path
               and not target.query and not target.fragment)
    if not live and not fixture:
        raise Rejected('GitHub target must be api.github.com or a loopback test fixture', 400)
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', artifact['repository']):
        raise Rejected('Repository must be owner/name', 400)
    if not re.fullmatch(r'[A-Za-z0-9_-]+(?:\[bot\])?', artifact['author']):
        raise Rejected('Pin the issue creator login', 400)
    if artifact['api_version'] != VERSION or artifact['limitations'] != LIMITATIONS:
        raise Rejected('GitHub version and evidence limitations must be explicit', 400)
    expected = artifact['expected']
    if (set(expected) != {'title_from', 'body_from', 'description'}
            or expected['title_from'] != 'payload.title' or expected['body_from'] != 'payload.body'
            or not isinstance(expected['description'], str) or not expected['description'].strip()):
        raise Rejected('Define observable title/body expectations', 400)
    if artifact['adapter'] != {'kind': 'github.issue.v1', 'page_limit': 10}:
        raise Rejected('Use the bounded GitHub issue adapter', 400)
    answers = artifact['interview']
    if (set(answers) != {'expected_behavior', 'sandbox', 'unknown_policy', 'marker_assumption'}
            or answers['expected_behavior'] != expected['description']
            or answers['sandbox'] != 'Dedicated repository: ' + artifact['repository']
            or answers['unknown_policy'] != 'Keep uncertain actions blocked'
            or answers['marker_assumption'] != 'Accepted: no copied or edited markers during recovery'):
        raise Rejected('Complete the GitHub interview and accept its evidence assumptions', 400)


def check_payload(payload):
    if (not isinstance(payload, dict) or set(payload) != {'title', 'body'}
            or not isinstance(payload['title'], str) or not 0 < len(payload['title']) <= 256
            or not isinstance(payload['body'], str) or len(payload['body']) > 4096
            or '<!-- causalrun:' in payload['body']):
        raise Rejected('Provide title/body only; body cannot contain reserved correlation markers', 400)


def marker(action_id, payload):
    return '\n\n<!-- causalrun:' + action_id + ':' + digest(payload) + ' -->'


def normalize(artifact, action_id, payload, issue):
    if not isinstance(issue, dict) or 'pull_request' in issue:
        raise Rejected('Evidence is not an issue')
    number, issue_id = issue.get('number'), issue.get('id')
    repository_url = artifact['target'] + '/repos/' + artifact['repository']
    if (type(number) is not int or number < 1 or type(issue_id) is not int or issue_id < 1
            or str(issue.get('repository_url', '')).lower() != repository_url.lower()
            or str(issue.get('url', '')).lower() != (repository_url + '/issues/' + str(number)).lower()
            or issue.get('user', {}).get('login') != artifact['author']
            or issue.get('title') != payload['title']
            or issue.get('body') != payload['body'] + marker(action_id, payload)):
        raise Rejected('Issue does not match target, creator, correlation, and expected content')
    return {'action_id': action_id, 'payload_digest': digest(payload),
            'result': {'title': issue['title'], 'body': payload['body'], 'issue_id': issue_id,
                       'number': number, 'url': issue['url'], 'repository': artifact['repository'],
                       'author': artifact['author']}}


def write(artifact, action_id, payload, token):
    status, issue, _ = request_with_headers(artifact['target'], '/repos/' + artifact['repository'] + '/issues',
                                           token, {'title': payload['title'],
                                                   'body': payload['body'] + marker(action_id, payload)},
                                           headers=HEADERS)
    if status != 201:
        raise Rejected('No GitHub creation receipt')
    return normalize(artifact, action_id, payload, issue)


def next_path(artifact, link, page):
    next_links = re.findall(r'<([^>]+)>;\s*rel="next"', link)
    if len(next_links) != 1:
        raise Rejected('Ambiguous or unsupported pagination')
    url = urlsplit(next_links[0])
    origin = urlsplit(artifact['target'])
    expected = '/repos/' + artifact['repository'] + '/issues'
    query = parse_qs(url.query, strict_parsing=True)
    if (url.scheme != origin.scheme or url.netloc != origin.netloc or url.path != expected
            or url.fragment or query != {'state': ['all'], 'per_page': ['100'],
                                        'sort': ['created'], 'direction': ['asc'], 'page': [str(page + 1)]}):
        raise Rejected('Pagination cannot change target, scope, or query')
    return url.path + '?' + url.query


def lookup(artifact, action_id, payload, token):
    path = '/repos/' + artifact['repository'] + '/issues?state=all&per_page=100&sort=created&direction=asc&page=1'
    candidates = []
    seen_ids = set()
    expected_marker = marker(action_id, payload)
    for page in range(1, artifact['adapter']['page_limit'] + 1):
        status, issues, headers = request_with_headers(artifact['target'], path, token, headers=HEADERS)
        if status != 200 or not isinstance(issues, list) or len(issues) > 100:
            raise Rejected('Issue listing is incomplete')
        for issue in issues:
            if not isinstance(issue, dict):
                raise Rejected('Malformed issue listing')
            issue_id = issue.get('id')
            if type(issue_id) is not int or issue_id in seen_ids:
                raise Rejected('Listing changed or repeated an issue')
            seen_ids.add(issue_id)
            body = issue.get('body') or ''
            if not isinstance(body, str):
                raise Rejected('Malformed issue body')
            if expected_marker in body:
                candidates.append(issue)
        link = next((value for key, value in headers.items() if key.lower() == 'link'), '')
        if 'rel="next"' not in link:
            if len(issues) == 100:
                raise Rejected('Full page without trustworthy completion evidence')
            break
        path = next_path(artifact, link, page)
    else:
        raise Rejected('Pagination budget exhausted')
    if len(candidates) != 1:
        raise Rejected('No unique correlated issue; keep outcome unknown')
    return normalize(artifact, action_id, payload, candidates[0])
