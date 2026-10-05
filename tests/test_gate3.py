import copy
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from causalrun import runtime, storage, validation, github
from causalrun.contracts import Rejected, digest
from causalrun.generation import build_github_contract
from examples.github_provider import create_server

SOURCE = (Path(__file__).resolve().parents[1] / 'examples/verify_github_issue.py').read_text()


def artifact(target='https://api.github.com', repository='sandbox/issues', author='tester', source=SOURCE):
    return build_github_contract(repository, author, source, {
        'expected_behavior': 'Create one issue with the requested title and body under the approved author',
        'sandbox': 'Dedicated repository: ' + repository,
        'unknown_policy': 'Keep uncertain actions blocked',
        'marker_assumption': 'Accepted: no copied or edited markers during recovery',
    }, target)


class GitHubTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp.name) / 'runtime.sqlite')
        storage.initialize(self.db)
        self.server = create_server()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.artifact = artifact(self.server.target)
        self.identifier = runtime.register(self.db, self.artifact)
        self.report = validation.validate(self.db, self.identifier)
        self.assertEqual(self.report['failed'], 0, self.report)
        runtime.approve(self.db, self.identifier, self.identifier, digest(self.report))
        self.payload = {'title': 'Test', 'body': 'Expected'}

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(5)
        self.temp.cleanup()

    def test_validation_cases_and_bad_verifier(self):
        self.assertEqual({c['name'] for c in self.report['cases']}, github.CASE_NAMES)
        bad = artifact(self.server.target, source='def verify(action_id, payload, evidence):\n    return True\n')
        identifier = runtime.register(self.db, bad)
        report = validation.validate(self.db, identifier)
        self.assertGreater(report['failed'], 0)
        with self.assertRaises(Rejected):
            runtime.approve(self.db, identifier, identifier, digest(report))

    def test_lost_response_recovers_without_repeat(self):
        self.server.drop_response = True
        action = runtime.execute(self.db, self.identifier, 'lost', self.payload, 'fixture-write')
        self.assertEqual(action['state'], 'IN_DOUBT')
        self.assertEqual(len(self.server.issues), 1)
        repeated = runtime.execute(self.db, self.identifier, 'lost', self.payload, 'fixture-write')
        self.assertEqual(repeated['id'], action['id'])
        self.assertEqual(self.server.posts, 1)
        recovered = runtime.verify(self.db, action['id'], 'fixture-read')
        self.assertEqual(recovered['state'], 'COMMITTED')
        reads = self.server.reads
        runtime.verify(self.db, action['id'], 'fixture-read')
        self.assertEqual(self.server.reads, reads)
        self.assertEqual(self.server.posts, 1)
        with self.assertRaises(Rejected):
            runtime.execute(self.db, self.identifier, 'lost', {'title': 'changed', 'body': ''}, 'fixture-write')

    def test_conflict_and_altered_evidence_block(self):
        self.server.drop_response = True
        action = runtime.execute(self.db, self.identifier, 'conflict', self.payload, 'fixture-write')
        original = copy.deepcopy(self.server.issues[0])
        duplicate = dict(original, id=2, number=2)
        self.server.issues.append(duplicate)
        self.assertEqual(runtime.verify(self.db, action['id'], 'fixture-read')['state'], 'IN_DOUBT')
        self.server.issues = [dict(original, body='Edited')]
        self.assertEqual(runtime.verify(self.db, action['id'], 'fixture-read')['state'], 'IN_DOUBT')
        self.server.issues = [original]
        self.assertEqual(runtime.verify(self.db, action['id'], 'wrong-token')['state'], 'IN_DOUBT')
        self.assertEqual(runtime.verify(self.db, action['id'], 'fixture-read')['state'], 'COMMITTED')
        self.assertEqual(self.server.posts, 1)

    def test_pagination_budget_and_full_page_fail_closed(self):
        item = {'id': 1, 'body': ''}
        with patch('causalrun.github.request_with_headers', return_value=(200, [dict(item, id=i) for i in range(100)], {})):
            with self.assertRaises(Rejected):
                github.lookup(self.artifact, 'missing', self.payload, 'fixture-read')
        calls = []
        def pages(target, path, token, **kwargs):
            page = len(calls) + 1; calls.append(path)
            issue = {'id': page, 'body': ''}
            link = '<' + target + '/repos/sandbox/issues/issues?state=all&per_page=100&sort=created&direction=asc&page=' + str(page + 1) + '>; rel="next"'
            return 200, [issue], {'Link': link}
        with patch('causalrun.github.request_with_headers', side_effect=pages):
            with self.assertRaises(Rejected):
                github.lookup(self.artifact, 'missing', self.payload, 'fixture-read')
        self.assertEqual(len(calls), 10)

    def test_untrusted_pagination_never_receives_credentials(self):
        self.server.untrusted_link = True
        before = self.server.reads
        with self.assertRaises(Rejected):
            github.lookup(self.artifact, 'missing', self.payload, 'fixture-read')
        self.assertEqual(self.server.reads - before, 1)

    def test_unapproved_and_reserved_marker_rejected(self):
        with storage.connect(self.db) as db:
            db.execute('DELETE FROM approvals')
        with self.assertRaises(Rejected):
            runtime.execute(self.db, self.identifier, 'unapproved', self.payload, 'fixture-write')
        self.assertEqual(self.server.posts, 0)
        with self.assertRaises(Rejected):
            github.check_payload({'title': 'test', 'body': '<!-- causalrun:fake -->'})
