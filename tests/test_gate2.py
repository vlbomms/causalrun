"""Generated source, selective interviews, and full-runtime recovery checks."""
import copy
import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from causalrun import discovery, generation, runtime, storage, validation
from causalrun.contracts import Rejected, canonical
from causalrun.transport import request
from causalrun.verifiers import compile_verifier
from tests.test_gate1 import Fixture, terminal_approval, PROVIDER_TOKEN, AGENT_TOKEN

ROOT = Path(__file__).resolve().parents[1]
READ_TOKEN = 'disposable-receipt-capability'
SOURCE = (ROOT / 'examples/verify_value.py').read_text()
OBSERVED_SCHEDULES = []
REJECTED_VERIFIERS = []


def prepared(target, ask=None):
    answers = iter(['1', '1', '1'])
    interview = discovery.interview(target + '/openapi.json', target,
                                    ask=ask or (lambda _: next(answers)), tell=lambda _: None)
    return generation.build_contract(interview, SOURCE)


class DiscoveryTests(unittest.TestCase):
    def test_openapi_facts_and_only_three_intent_questions(self):
        facts = discovery.inspect_api(str(ROOT / 'examples/openapi.json'))
        self.assertEqual(facts['authentication']['providerBearer']['scheme'], 'bearer')
        self.assertEqual(facts['operations'][0]['method'], 'POST')
        self.assertEqual({item['id'] for item in discovery.questions()},
                         {'expected_behavior', 'sandbox', 'unknown_policy'})
        self.assertTrue(all(item['free_text'] and len(item['options']) == 2
                            for item in discovery.questions()))

    def test_interview_accepts_free_text_and_no_discovery_report(self):
        answers = iter(['Exact matching value and original action ID', '1', '2'])
        output = discovery.interview(str(ROOT / 'examples/openapi.json'), 'http://127.0.0.1:8090',
                                     ask=lambda _: next(answers), tell=lambda _: None)
        self.assertEqual(output['answers']['expected_behavior'], 'Exact matching value and original action ID')
        self.assertEqual(set(output), {'target', 'source', 'operation_id', 'api_version', 'answers'})

    def test_no_sandbox_or_unsafe_repeat_policy_stops_preparation(self):
        for values in (['1', '2', '1'], ['1', '1', 'retry blindly']):
            answers = iter(values)
            with self.assertRaises(Rejected):
                discovery.interview(str(ROOT / 'examples/openapi.json'), 'http://127.0.0.1:8090',
                                     ask=lambda _: next(answers), tell=lambda _: None)

    def test_swagger_reference_and_wsdl_inspection(self):
        document = {'swagger': '2.0', 'info': {'version': '1'}, 'definitions': {'Input': {'type': 'object'}},
                    'paths': {'/write': {'post': {'parameters': [{'in': 'body', 'schema': {'$ref': '#/definitions/Input'}}]}}}}
        with patch('causalrun.discovery.read_description', return_value=document):
            facts = discovery.inspect_api('ignored')
        self.assertEqual(facts['operations'][0]['request_schema'], {'type': 'object'})
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'service.wsdl'
            path.write_text('<definitions xmlns="http://schemas.xmlsoap.org/wsdl/"><portType><operation name="Create"/></portType></definitions>')
            facts = discovery.inspect_api(str(path))
        self.assertEqual(facts['format'], 'wsdl')
        self.assertEqual(facts['operations'], ['Create'])

    def test_verifier_rejects_side_effects_and_unbounded_code(self):
        bad = [
            "import os\ndef verify(action_id,payload,evidence): return True",
            "def verify(action_id,payload,evidence): return open('/tmp/secret')",
            "def verify(action_id,payload,evidence): return evidence.__class__",
            "def verify(action_id,payload,evidence):\n while True: pass",
            "def verify(action_id,payload,evidence): return [x for x in evidence]",
            "def verify(action_id,payload,evidence): return",
        ]
        for source in bad:
            with self.subTest(source=source), self.assertRaises(Rejected):
                compile_verifier(source)


class GeneratedTests(Fixture):
    def setUp(self):
        super().setUp()
        self.provider.receipt_token = READ_TOKEN
        self.server.receipt_token = READ_TOKEN
        self.server.receipt_credentials_configured = True
        self.artifact = prepared(self.target)
        self.identifier = runtime.register(self.db, self.artifact)

    def ready(self):
        report = validation.validate(self.db, self.identifier)
        self.assertEqual((report['passed'], report['failed']), (10, 0), report)
        self.assertEqual(report['false_successes'], 0)
        self.assertEqual(report['false_failures'], 0)
        code, output = terminal_approval(self.db, self.identifier)
        self.assertEqual(code, 0, output)

    def test_generated_code_survives_source_file_removal_and_restart(self):
        file = Path(self.directory.name) / 'generated_verifier.py'
        file.write_text(SOURCE)
        self.assertEqual(self.artifact['verifier']['source'], file.read_text())
        file.unlink()
        self.ready()
        action = self.execute()
        self.assertEqual(action['state'], 'COMMITTED')
        storage.initialize(self.db)
        with storage.connect(self.db) as db:
            artifact = runtime.load_connector(db, self.identifier)
        self.assertEqual(artifact['verifier']['source'], SOURCE)
        self.assertEqual(self.execute(), action)
        self.assertEqual(self.counts(), {'objects': 1, 'writes': 1})

    def test_generated_verifier_handles_unicode_and_json_characters(self):
        self.ready()
        for index, value in enumerate(['', 'λ and emoji 🙂', 'quotes " and newline\n']):
            action = self.execute(key='unicode-' + str(index), value=value)
            self.assertEqual(action['state'], 'COMMITTED')
            self.assertEqual(action['receipt']['result']['value'], value)
        self.assertEqual(self.counts(), {'objects': 3, 'writes': 3})

    def test_changed_verifier_rejected_before_dispatch(self):
        self.ready()
        artifact = copy.deepcopy(self.artifact)
        artifact['verifier']['source'] = 'def verify(action_id, payload, evidence): return True\n'
        other = runtime.register(self.db, artifact)
        self.rejected(lambda: self.execute(identifier=other), 409)
        with storage.connect(self.db) as db:
            db.execute('UPDATE connectors SET artifact=? WHERE digest=?', (canonical(artifact), self.identifier))
        self.rejected(self.execute, 409)
        self.assertEqual(self.counts(), {'objects': 0, 'writes': 0})

    def test_bad_generated_verifiers_fail_validation(self):
        for verdict in ('True', 'False'):
            artifact = copy.deepcopy(self.artifact)
            artifact['verifier']['source'] = 'def verify(action_id, payload, evidence): return ' + verdict + '\n'
            identifier = runtime.register(self.db, artifact)
            report = validation.validate(self.db, identifier)
            self.assertGreater(report['failed'], 0)
            REJECTED_VERIFIERS.append({'injected_source': artifact['verifier']['source'], 'validation': report})
            code, output = terminal_approval(self.db, identifier)
            self.assertEqual(code, 1, output)
            self.rejected(lambda: self.execute(identifier=identifier), 409)
        self.assertEqual(self.counts(), {'objects': 0, 'writes': 0})

    def test_lost_response_recovered_without_second_write(self):
        self.ready()
        self.provider.fault_mode = 'drop_response'
        action = self.execute()
        self.assertEqual(action['state'], 'IN_DOUBT')
        recovered = request(self.base, '/v1/actions/' + action['id'] + '/verify', AGENT_TOKEN, {})[1]
        self.assertEqual(recovered['state'], 'COMMITTED')
        self.assertEqual(self.execute()['id'], action['id'])
        self.assertEqual(self.counts(), {'objects': 1, 'writes': 1})

    def test_delayed_commit_remains_unknown_until_commit(self):
        self.ready()
        self.provider.fault_mode = 'delay_commit'
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.execute)
            self.assertTrue(self.provider.request_received.wait(timeout=5))
            repeat = self.execute()
            self.assertEqual(repeat['state'], 'IN_DOUBT')
            check = request(self.base, '/v1/actions/' + repeat['id'] + '/verify', AGENT_TOKEN, {})[1]
            self.assertEqual(check['state'], 'IN_DOUBT')
            self.assertEqual(self.counts(), {'objects': 0, 'writes': 0})
            self.provider.allow_commit.set()
            completed = pending.result(timeout=5)
            self.assertEqual(completed['state'], 'COMMITTED')
        self.assertEqual(self.counts(), {'objects': 1, 'writes': 1})
        OBSERVED_SCHEDULES.append({'schedule': 'POST paused before commit; inspect while pending; release commit',
                                   'before_commit': check, 'after_commit': completed, 'provider_counts': self.counts()})

    def test_missing_and_misleading_evidence_block_then_recover(self):
        self.ready()
        for mode in ('missing_receipt', 'wrong_action', 'wrong_payload', 'wrong_value', 'verifier_error'):
            self.provider.fault_mode = 'drop_response'
            action = self.execute(key=mode)
            self.assertEqual(action['state'], 'IN_DOUBT')
            self.provider.fault_mode = mode
            check = request(self.base, '/v1/actions/' + action['id'] + '/verify', AGENT_TOKEN, {})[1]
            self.assertEqual(check['state'], 'IN_DOUBT', mode)
            self.assertEqual(self.execute(key=mode)['state'], 'IN_DOUBT')
            self.provider.fault_mode = 'none'
            recovered = request(self.base, '/v1/actions/' + action['id'] + '/verify', AGENT_TOKEN, {})[1]
            self.assertEqual(recovered['state'], 'COMMITTED')
            OBSERVED_SCHEDULES.append({'schedule': 'Commit then lose response; receipt fault; clear fault; verify',
                                       'fault': mode, 'uncertain': check, 'recovered': recovered,
                                       'provider_counts': self.counts()})
        self.assertEqual(self.counts(), {'objects': 5, 'writes': 5})

    def test_receipt_credential_cannot_write(self):
        self.ready()
        with self.assertRaises(HTTPError) as context:
            request(self.target, '/values', READ_TOKEN, {})
        self.assertEqual(context.exception.code, 401)
        self.server.receipt_credentials_configured = False
        self.rejected(self.execute, 400)
        self.assertEqual(self.counts(), {'objects': 0, 'writes': 0})


if __name__ == '__main__':
    unittest.main()
