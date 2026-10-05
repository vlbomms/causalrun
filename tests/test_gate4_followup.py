"""Additional identity and lifecycle checks after the full gate 4 regression."""
import json
import os
import stat
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from causalrun import native, storage
from causalrun.transport import request
from tests import test_gate4
ROOT = test_gate4.ROOT


class FollowupTests(unittest.TestCase):
    setUp = test_gate4.NativeTests.setUp
    tearDown = test_gate4.NativeTests.tearDown

    def test_github_identity_change_requires_review_before_send(self):
        fields = {'operation': 'github.issue.create.v1', 'repository': 'sandbox/issues'}
        review = native.prepare(self.db, dict(fields,
            source=(ROOT / 'examples/verify_github_issue.py').read_text(), answers={
                'expected_behavior': 'Exact title and body', 'sandbox': 'Dedicated repository: sandbox/issues',
                'unknown_policy': 'Keep uncertain actions blocked',
                'marker_assumption': 'Accepted: no copied or edited markers during recovery'}), 'tester')
        self.assertEqual(review['validation']['failed'], 0)
        self.server.credential_operation = 'github.issue.create.v1'
        self.server.github_author = 'tester'
        _, approved = request(self.url, '/native/approve', self.server.operator_token, {
            'connector_digest': review['connector_digest'], 'report_digest': review['report_digest'], 'scope': fields})
        self.assertTrue(approved['ready'])
        self.server.github_author = 'another-account'
        _, lookup = request(self.url, '/native/lookup', 'native-agent-token-long', fields)
        self.assertFalse(lookup['ready'])
        with self.assertRaises(HTTPError):
            request(self.url, '/v1/actions', 'native-agent-token-long', {
                'connector_digest': review['connector_digest'], 'action_key': 'identity-change',
                'payload': {'title': 'test', 'body': 'test'}})
        with storage.connect(self.db) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM actions').fetchone()[0], 0)

    def test_authenticated_lifecycle_and_private_permissions(self):
        state = self.folder / 'lifecycle'
        with patch.dict(os.environ, {'CAUSALRUN_PROVIDER_TOKEN': 'native-write-token-long',
                                      'CAUSALRUN_RECEIPT_TOKEN': 'native-read-token-long'}):
            try:
                first = native.ensure(state)
                second = native.ensure(state)
                self.assertEqual(first['pid'], second['pid'])
                self.assertEqual(first['instance'], second['instance'])
                self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE((state / 'capabilities.json').stat().st_mode), 0o600)
                # A forged endpoint must not be used as a credential destination or killed.
                service = json.loads((state / 'service.json').read_text())
                native.private_json(state / 'service.json', dict(service, url='https://untrusted.invalid'))
                self.assertIsNone(native.running(state))
                self.assertEqual(native.stop(state), {'stopped': False})
                native.private_json(state / 'service.json', service)
                self.assertEqual(native.stop(state), {'stopped': True})
                self.assertEqual(native.stop(state), {'stopped': False})
            finally:
                native.stop(state)
