"""Local acceptance for the generic contract used by the live sandbox test."""
import copy
import tempfile
import unittest
from pathlib import Path
from causalrun import runtime, storage, validation
from causalrun.contracts import Rejected, check_artifact
from causalrun.generation import build_http_contract
from causalrun.http_json import binding
from causalrun.verifiers import confirms
from examples.github_json_contract import github_json_contract


class LiveContractTests(unittest.TestCase):
    def setUp(self):
        self.contract, self.source = github_json_contract('vlbomms/tempo', 'vlbomms')
        self.artifact = build_http_contract(self.contract, self.source)
        self.payload = self.contract['fixture']['payload']
        self.evidence = binding(self.contract['fixture']['evidence'], 'original', self.payload)

    def test_github_per_page_and_supplied_fixtures_validate(self):
        self.assertEqual(self.artifact['adapter']['read']['pagination']['size'], 'per_page')
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'runtime.sqlite')
            storage.initialize(path)
            identifier = runtime.register(path, self.artifact)
            report = validation.validate(path, identifier)
            self.assertEqual(report['passed'], 4)
            self.assertEqual(report['failed'], 0)
            self.assertEqual(report['provider_requests'], 0)

    def test_positive_object_and_list_match(self):
        for evidence in (self.evidence, [self.evidence]):
            self.assertTrue(confirms(self.source, 'original', self.payload, evidence))

    def test_conflict_wrong_author_repo_title_and_marker_block(self):
        negatives = [[self.evidence, self.evidence]]
        for field, value in [('title', 'wrong'), ('body', 'edited marker'),
                             ('user', {'login': 'someone-else'}), ('repository_url', 'https://api.github.com/repos/other/repo'),
                             ('pull_request', {})]:
            evidence = dict(self.evidence)
            evidence[field] = value
            negatives.append(evidence)
        for evidence in negatives:
            with self.subTest(evidence=evidence):
                self.assertFalse(confirms(self.source, 'original', self.payload, evidence))

    def test_bad_pagination_configuration_is_rejected(self):
        for changes in ({'limit': 11}, {'page_size': 0}, {'page': 'per_page'}, {'size': 'bad\r\nname'}):
            candidate = copy.deepcopy(self.artifact)
            candidate['adapter']['read']['pagination'].update(changes)
            with self.subTest(changes=changes), self.assertRaises(Rejected):
                check_artifact(candidate)
