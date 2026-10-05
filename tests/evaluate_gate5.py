"""Recorded mechanical workflow comparison; no human-time or model-quality claims."""
import hashlib
import json
import statistics
import time
from pathlib import Path
from tests.demo_gate2 import scenario
from tests.demo_gate4 import demonstration
from tests.opencode_fixture import create_model

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'docs/results/gate-5'


def manual():
    report = scenario('lost_response', evaluate=True)
    assert len(report['operator_commands']) == 11, report['operator_commands']
    return {'condition': 'manual', 'passed': True, 'operator_commands': len(report['operator_commands']),
            'questions': report['interview']['questions_answered'], 'approvals': 1, 'source_candidates': 2,
            'injected_corrections': 1, 'elapsed_seconds': report['workflow_elapsed_seconds'],
            'provider_counts': report['provider_counts'], 'negative_validation_failures': report['negative_validation']['failed'],
            'result': report}


def assisted():
    report = demonstration(model_factory=lambda target: create_model(target, repair=True))
    assert (report['passed'], report['failed']) == (2, 0), report.get('failure_message')
    tools = [part for message in report['first_session_messages'] for part in message.get('parts', []) if part.get('tool') == 'causalrun_prepare']
    candidates = [json.loads(tool['state']['output']) for tool in tools]
    assert len(candidates) == 2 and candidates[0]['status'] == 'VALIDATION_FAILED', candidates
    return {'condition': 'assisted', 'passed': True, 'operator_commands': 0,
            'questions': sum(len(q['questions']) for q in report['questions']), 'approvals': len(report['permissions']),
            'source_candidates': len(candidates), 'injected_corrections': 1,
            'elapsed_seconds': report['workflow_elapsed_seconds'], 'provider_counts': report['final_counts'],
            'negative_validation_failures': candidates[0]['validation']['failed'], 'result': report}


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = {'command': 'python3 -m tests.evaluate_gate5', 'protocol': 'evaluation-protocol.md',
              'trials': [], 'failed': 0, 'authoring_time': None, 'live_model_generation': False,
              'hashes': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                         for name in ('examples/openapi.json', 'examples/verify_value.py')}}
    for pair, order in enumerate(((manual, assisted), (assisted, manual), (manual, assisted)), 1):
        for condition in order:
            try:
                trial = condition(); trial['pair'] = pair
                report['trials'].append(trial)
            except Exception as error:
                report['failed'] += 1
                report['trials'].append({'pair': pair, 'condition': condition.__name__, 'passed': False, 'failure': str(error)})
            (OUTPUT / 'evaluation.json').write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps({'pair': pair, 'condition': condition.__name__, 'passed': report['trials'][-1]['passed']}), flush=True)
    report['medians'] = {}
    for name in ('manual', 'assisted'):
        trials = [trial for trial in report['trials'] if trial['condition'] == name and trial['passed']]
        if len(trials) == 3:
            report['medians'][name] = {metric: statistics.median(trial[metric] for trial in trials)
                                       for metric in ('operator_commands', 'questions', 'approvals', 'injected_corrections', 'elapsed_seconds')}
    report['passed'] = sum(trial['passed'] for trial in report['trials'])
    (OUTPUT / 'evaluation.json').write_text(json.dumps(report, indent=2) + '\n')
    return 0 if report['passed'] == 6 and report['failed'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
