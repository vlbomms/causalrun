"""Documented success needs no interview answer; genuine ambiguity blocks setup."""
import unittest
from causalrun import native, storage
from causalrun.contracts import Rejected
from causalrun.transport import request
from tests import test_gate4


class SelectiveQuestionsTests(unittest.TestCase):
    setUp = test_gate4.NativeTests.setUp
    tearDown = test_gate4.NativeTests.tearDown

    def inputs(self, **overrides):
        return dict(self.fields, source=test_gate4.SOURCE, api_version='1',
                    answers={'sandbox': 'Yes, only the disposable fixture', 'unknown_policy': 'Keep blocked and request review'}, **overrides)

    def test_documented_success_omits_success_question_and_prepares(self):
        _, guide = request(self.url, '/native/lookup', 'native-agent-token-long', self.fields)
        self.assertEqual([question['id'] for question in guide['questions']], ['sandbox', 'unknown_policy'])
        self.assertEqual(guide['documented_success']['origin'], 'API profile, not a user answer')
        review = native.prepare(self.db, self.inputs(), None)
        self.assertEqual(review['validation']['failed'], 0)
        self.assertEqual(review['artifact']['expected']['description'], guide['documented_success']['expected_behavior'])
        self.assertEqual(review['artifact']['verifier']['source'], test_gate4.SOURCE)
        with storage.connect(self.provider.db_path) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM requests').fetchone()[0], 0)

    def test_ambiguity_preserved_over_http_and_requires_actual_answer(self):
        fields = dict(self.fields, needs_success_clarification=True)
        _, guide = request(self.url, '/native/lookup', 'native-agent-token-long', fields)
        self.assertEqual(guide['questions'][0]['id'], 'expected_behavior')
        with self.assertRaises(Rejected): native.prepare(self.db, self.inputs(needs_success_clarification=True), None)
        inputs = self.inputs(needs_success_clarification=True)
        inputs['answers']['expected_behavior'] = 'Exact stored value with evidence for this original action'
        review = native.prepare(self.db, inputs, None)
        self.assertEqual(review['artifact']['expected']['description'], inputs['answers']['expected_behavior'])
        self.assertEqual(review['validation']['failed'], 0)

    def test_consent_and_invalid_flags_are_not_inferred(self):
        for missing in ('sandbox', 'unknown_policy'):
            inputs = self.inputs(); del inputs['answers'][missing]
            with self.assertRaises(Rejected): native.prepare(self.db, inputs, None)
        for invalid in ('false', 1, None):
            with self.assertRaises(Rejected): native.binding(self.db, dict(self.fields, needs_success_clarification=invalid))

    def test_ambiguous_request_does_not_reuse_approval_silently(self):
        review = native.prepare(self.db, self.inputs(), None)
        request(self.url, '/native/approve', self.server.operator_token, {
            'connector_digest': review['connector_digest'], 'report_digest': review['report_digest'], 'scope': self.fields})
        self.assertTrue(native.binding(self.db, self.fields)['ready'])
        self.assertFalse(native.binding(self.db, dict(self.fields, needs_success_clarification=True))['ready'])

    def test_github_documented_success_retains_assumption_consent(self):
        fields = {'operation': 'github.issue.create.v1', 'repository': 'sandbox/issues'}
        guide = native.preparation_guide(fields, 'tester')
        self.assertNotIn('expected_behavior', [question['id'] for question in guide['questions']])
        self.assertIn('marker_assumption', [question['id'] for question in guide['questions']])
        inputs = dict(fields, source=(test_gate4.ROOT / 'examples/verify_github_issue.py').read_text(), answers={
            'sandbox': 'Dedicated repository: sandbox/issues', 'unknown_policy': 'Keep uncertain actions blocked',
            'marker_assumption': 'Accepted: no copied or edited markers during recovery'})
        review = native.prepare(self.db, inputs, 'tester')
        self.assertEqual(review['validation']['failed'], 0)
