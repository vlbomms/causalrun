"""GitHub issue example expressed entirely as a generic HTTP/JSON contract."""
import json
import re


def github_json_contract(repository, author):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Use owner/repository')
    if not re.fullmatch(r'[A-Za-z0-9_-]+(?:\[bot\])?', author):
        raise ValueError('Use the authenticated GitHub login')
    owner, repo = repository.split('/')
    body = {'$text': [{'$bind': 'payload', 'path': ['body']}, '\n\n<!-- causalrun:',
                      {'$bind': 'action_id'}, ' -->']}
    match = 'unique_match(evidence, "body", payload["body"] + "\\n\\n<!-- causalrun:" + action_id + " -->")'
    source = ('def verify(action_id, payload, evidence):\n    return isinstance(' + match + ', dict)'
              ' and "pull_request" not in ' + match +
              ' and ' + match + '["title"] == payload["title"]'
              ' and ' + match + '["user"]["login"] == ' + json.dumps(author) +
              ' and ' + match + '["repository_url"] == ' + json.dumps('https://api.github.com/repos/' + repository) + '\n')
    headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2026-03-10'}
    path = ['repos', owner, repo, 'issues']
    contract = {
        'name': 'github-json-issue-' + repository.replace('/', '-'), 'target': 'https://api.github.com',
        'api_version': '2026-03-10', 'expected': 'One issue with the requested title, marked body, repository, and approved author',
        'adapter': {
            'write': {'method': 'POST', 'path': path, 'query': {}, 'headers': headers, 'statuses': [201],
                      'body': {'title': {'$bind': 'payload', 'path': ['title']}, 'body': body}},
            'read': {'method': 'GET', 'path': path, 'query': {'state': 'all', 'sort': 'created', 'direction': 'desc'},
                     'headers': headers, 'statuses': [200],
                     'pagination': {'page': 'page', 'size': 'per_page', 'page_size': 10, 'limit': 10}}},
        'authentication': {'write': {'type': 'bearer', 'secret': 'CAUSALRUN_GITHUB_TOKEN'},
                           'read': {'type': 'bearer', 'secret': 'CAUSALRUN_GITHUB_TOKEN'}},
        'fixture': {'payload': {'title': 'fixture issue', 'body': 'fixture body'},
                    'different_payload': {'title': 'other issue', 'body': 'other body'},
                    'evidence': {'title': 'fixture issue', 'body': body, 'user': {'login': author},
                                 'repository_url': 'https://api.github.com/repos/' + repository}},
        'limitations': ['Missing evidence does not prove non-execution',
                        'Fixture checks do not prove provider guarantees',
                        'Marker matching assumes no copied or edited marker during recovery',
                        'Page-number listings are bounded and not a consistent snapshot',
                        'The configured token may have write access during evidence reads'],
        'sources': ['https://docs.github.com/en/rest/issues/issues',
                    'https://docs.github.com/en/rest/using-the-rest-api/using-pagination-in-the-rest-api']}
    return contract, source
