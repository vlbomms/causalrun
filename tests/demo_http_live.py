"""One authorized tempo issue through the generic adapter; close only that issue."""
import argparse
import hashlib
import json
import os
import platform
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from causalrun import http_json, runtime, storage, validation
from causalrun.contracts import digest
from causalrun.generation import build_http_contract
from causalrun.transport import request_with_headers
from examples.github_json_contract import github_json_contract

REPOSITORY = 'vlbomms/tempo'  # User-authorized dedicated sandbox; never accept another target silently.
ROOT = Path(__file__).resolve().parents[1]


def gh_json(path):
    return json.loads(subprocess.check_output(['gh', 'api', path], text=True, stderr=subprocess.DEVNULL))


def gh_json_pages(path):
    return json.loads(subprocess.check_output(['gh', 'api', '--paginate', '--slurp', path],
                                             text=True, stderr=subprocess.DEVNULL))


def demonstrate():
    output = ROOT / 'docs/results/http-gate-d'
    output.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder = ROOT / '.local/http-live' / stamp
    folder.mkdir(parents=True, mode=0o700, exist_ok=False)
    path = str(folder / 'runtime.sqlite')
    storage.initialize(path)
    report = {'recorded_at': datetime.now(timezone.utc).isoformat(),
              'command': 'python3 -m tests.demo_http_live --live', 'repository': REPOSITORY,
              'versions': {'python': sys.version, 'sqlite': sqlite3.sqlite_version, 'platform': platform.platform(),
                           'gh': subprocess.check_output(['gh', '--version'], text=True).splitlines()[0]},
              'approval': 'User authorized sandbox tests; test harness calls operator approval in an isolated state directory',
              'fault': 'Real POST response is received by the test interceptor, then withheld from the runtime; no actual network outage claimed',
              'runtime_database': str(folder.relative_to(ROOT) / 'runtime.sqlite'),
              'requests': {'connector_writes': 0, 'connector_reads': 0, 'oracle_reads': 0, 'cleanup_writes': 0},
              'passed': 0, 'failed': 0}
    created = None
    owned = False
    token = None
    original = http_json.request_json
    def observed(artifact, kind, action_id, payload, page=None, deadline=None):
        nonlocal created
        report['requests']['connector_writes' if kind == 'write' else 'connector_reads'] += 1
        value = original(artifact, kind, action_id, payload, page, deadline)
        if kind == 'write':
            created = value
            raise OSError('Test-only withheld write response')
        return value
    try:
        repo = gh_json('repos/' + REPOSITORY)
        user = gh_json('user')
        assert repo['full_name'] == REPOSITORY and repo['has_issues']
        assert repo.get('permissions', {}).get('push'), 'No sandbox write permission'
        token = subprocess.check_output(['gh', 'auth', 'token', '--hostname', 'github.com'],
                                        text=True, stderr=subprocess.DEVNULL).strip()
        contract, source = github_json_contract(REPOSITORY, user['login'])
        with patch.dict(os.environ, {'CAUSALRUN_GITHUB_TOKEN': token}), patch.object(http_json, 'request_json', observed):
            artifact = build_http_contract(contract, source)
            identifier = runtime.register(path, artifact)
            evidence = validation.validate(path, identifier)
            assert evidence['failed'] == 0
            runtime.approve(path, identifier, identifier, digest(evidence))
            payload = {'title': 'causalrun generic API test ' + stamp,
                       'body': 'Authorized disposable test of generic HTTP/JSON write recovery.'}
            action = runtime.execute(path, identifier, 'http-live/' + stamp, payload, '')
            report['artifact'], report['validation'] = artifact, evidence
            report['after_lost_response'] = action
            assert action['state'] == 'IN_DOUBT'
            assert created is not None
            assert created['title'] == payload['title'] and created['user']['login'] == user['login']
            assert created['repository_url'] == 'https://api.github.com/repos/' + REPOSITORY
            expected_body = payload['body'] + '\n\n<!-- causalrun:' + action['id'] + ' -->'
            assert created['body'] == expected_body
            assert type(created['number']) is int and created['number'] > 0
            owned = True
            # Independent read path bypasses the generated verifier and generic adapter.
            oracle = gh_json('repos/' + REPOSITORY + '/issues/' + str(created['number']))
            report['requests']['oracle_reads'] += 1
            assert oracle['title'] == payload['title'] and oracle['body'] == expected_body
            assert oracle['user']['login'] == user['login']
            pages = gh_json_pages('repos/' + REPOSITORY + '/issues?state=all&per_page=100')
            report['requests']['oracle_reads'] += len(pages)
            matches = [item for page in pages for item in page
                       if item.get('body') == expected_body and item.get('user', {}).get('login') == user['login']]
            assert len(matches) == 1 and matches[0]['number'] == created['number']
            report['oracle'] = {'number': oracle['number'], 'url': oracle['html_url'], 'title': oracle['title'],
                                'body': oracle['body'], 'author': oracle['user']['login'], 'state': oracle['state'],
                                'matching_objects': len(matches)}
            recovered = runtime.verify(path, action['id'], '')
            assert recovered['state'] == 'COMMITTED'
            report['recovered'] = recovered
            repeated = runtime.execute(path, identifier, 'http-live/' + stamp, payload, '')
            assert repeated['id'] == recovered['id'] and repeated['state'] == 'COMMITTED'
            assert runtime.result(path, recovered['id']) == repeated
            assert report['requests']['connector_writes'] == 1
            report['repeated_action_id'] = repeated['id']
            report['passed'] = 1
    except Exception as error:
        report['failed'] = 1
        report['error_type'] = type(error).__name__
        # Never record raw provider exceptions, subprocess output, or tokens.
        report['error'] = 'Live acceptance did not complete; inspect the isolated action and recorded request counts'
    finally:
        if owned and token:
            try:
                number = created['number']
                report['requests']['cleanup_writes'] += 1
                status, closed, _ = request_with_headers('https://api.github.com',
                    '/repos/' + REPOSITORY + '/issues/' + str(number), token,
                    {'state': 'closed'}, method='PATCH', headers={'X-GitHub-Api-Version': '2026-03-10'})
                assert status == 200 and closed['state'] == 'closed'
                report['cleanup'] = {'number': number, 'state': closed['state'], 'url': closed['html_url']}
            except Exception:
                report['failed'] = 1
                report['cleanup'] = {'state': 'UNCONFIRMED', 'instruction': 'Check only the issue created by this test; do not repeat its creation'}
        sources = [p for folder_name in ('causalrun', 'examples', 'adapters', 'tests')
                   for p in sorted((ROOT / folder_name).rglob('*'))
                   if p.suffix in ('.py', '.mjs', '.json') and '__pycache__' not in str(p)]
        report['source_hashes'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
        (output / ('live-' + stamp + '.json')).write_text(json.dumps(report, indent=2) + '\n')
        (output / 'live.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Perform one authorized sandbox write and cleanup')
    parser.add_argument('--resume', help='Read-only recovery of a recorded live run; never create another issue')
    args = parser.parse_args()
    if args.resume:
        report = resume(Path(args.resume))
        print(json.dumps({k: report[k] for k in ('passed', 'failed', 'requests')}))
        return 0 if report['failed'] == 0 else 1
    if not args.live:
        parser.error('Use --live only with user authorization for ' + REPOSITORY)
    report = demonstrate()
    print(json.dumps({k: report[k] for k in ('passed', 'failed', 'requests')}))
    if 'cleanup' in report:
        print(json.dumps(report['cleanup']))
    return 0 if report['failed'] == 0 else 1


def resume(previous):
    previous = previous.resolve()
    original = json.loads(previous.read_text())
    assert original['repository'] == REPOSITORY
    folder = (ROOT / original['runtime_database']).resolve()
    assert (ROOT / '.local/http-live').resolve() in folder.parents
    action = original['after_lost_response']
    report = {'recorded_at': datetime.now(timezone.utc).isoformat(),
              'command': 'python3 -m tests.demo_http_live --resume ' + str(previous.relative_to(ROOT)),
              'repository': REPOSITORY, 'prior_failed_run': str(previous.relative_to(ROOT)),
              'versions': original['versions'], 'requests': dict(original['requests']),
              'recovery_only': True, 'passed': 0, 'failed': 0, 'cleanup': original.get('cleanup')}
    token = subprocess.check_output(['gh', 'auth', 'token', '--hostname', 'github.com'],
                                   text=True, stderr=subprocess.DEVNULL).strip()
    real = http_json.request_json
    def reads_only(artifact, kind, action_id, payload, page=None, deadline=None):
        assert kind == 'read', 'Resume must never dispatch a write'
        report['requests']['connector_reads'] += 1
        return real(artifact, kind, action_id, payload, page, deadline)
    try:
        with patch.dict(os.environ, {'CAUSALRUN_GITHUB_TOKEN': token}), patch.object(http_json, 'request_json', reads_only):
            recovered = runtime.verify(str(folder), action['id'], '')
            report['recovered'] = recovered
            assert recovered['state'] == 'COMMITTED'
            pages = gh_json_pages('repos/' + REPOSITORY + '/issues?state=all&per_page=100')
            report['requests']['oracle_reads'] += len(pages)
            expected = action['payload']['body'] + '\n\n<!-- causalrun:' + action['id'] + ' -->'
            matches = [item for page in pages for item in page if item.get('body') == expected]
            assert len(matches) == 1 and matches[0]['title'] == action['payload']['title']
            report['oracle'] = {'matching_objects': len(matches), 'number': matches[0]['number'],
                                'url': matches[0]['html_url'], 'state': matches[0]['state']}
            repeated = runtime.execute(str(folder), action['connector_digest'], action['action_key'], action['payload'], '')
            assert repeated['id'] == action['id'] and repeated['state'] == 'COMMITTED'
            assert runtime.result(str(folder), action['id']) == repeated
            report['repeated_action_id'] = repeated['id']
            assert report['requests']['connector_writes'] == 1
            report['passed'] = 1
    except Exception as error:
        report['failed'] = 1
        report['error_type'] = type(error).__name__
        report['error'] = 'Read-only recovery did not confirm the original action'
    report['source_hashes'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in (ROOT / 'causalrun').glob('*.py')}
    output = ROOT / 'docs/results/http-gate-d'
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    (output / ('live-resume-' + stamp + '.json')).write_text(json.dumps(report, indent=2) + '\n')
    (output / 'live.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    raise SystemExit(main())
