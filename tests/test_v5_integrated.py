"""Versioned V5 integration checks through the ORIGINAL LangGraph recording/replay harness.

All models in these tests are explicitly deterministic fake tool emitters, not providers.
"""
import json
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from oracle import reference_answer, simulate, patch_facts
from agent_graph import GraphEnvironment, agent_prompt, replay_record
from benchmarks.spec import reference_trajectory, source_case, get_spec, service_codes
from run_graph_agent import run_episode

TASKS = [f'RW{i:02d}V5' for i in range(1, 7)]

class ReferenceGraph:
    def __init__(self, env, unsafe=False, bogus_evidence=False, wrong_cause=False):
        self.env, self.unsafe, self.bogus_evidence, self.wrong_cause = env, unsafe, bogus_evidence, wrong_cause

    def stream(self, _input, config, stream_mode):
        for idx, (tool, args) in enumerate(reference_trajectory(self.env.task_id), 1):
            args = deepcopy(args)
            if self.unsafe and tool == 'apply_repair':
                args['action_id'] = 'A90'
            if self.bogus_evidence and tool == 'submit_diagnosis':
                args['evidence_ids'] = ['EV001', 'EV002']
            if self.wrong_cause and tool == 'submit_diagnosis':
                args['root_cause_id'] = 'H05' if args['root_cause_id'] != 'H05' else 'H04'
            ident = f'offline-{idx}'
            yield {'model': {'messages': [SimpleNamespace(
                type='ai', content='', tool_calls=[{'name': tool, 'args': args, 'id': ident}],
                usage_metadata={}, response_metadata={}, additional_kwargs={}, id=ident)]}}
            observation = self.env.execute(tool, args, ident)
            yield {'tools': {'messages': [SimpleNamespace(type='tool', content=observation)]}}


def run_mock(task, **changes):
    return run_episode(task, 'mock/offline:free', 1, 'fake-token', 2000, 'low', 0, 3,
                       graph_factory=lambda env, *_: ReferenceGraph(env, **changes))

class V5IntegratedTests(unittest.TestCase):
    def test_reference_replays_strictly_all_six(self):
        for task in TASKS:
            with self.subTest(task=task):
                record = run_mock(task)
                self.assertEqual(record['status'], 'completed')
                self.assertTrue(record['replay_verified'])
                self.assertTrue(record['grade']['strict_pass'])
                self.assertEqual(record['grade']['pass_contract'], 'outcome-v5')
                self.assertTrue(replay_record(record)['verified'])
                self.assertNotIn('incident_name', json.loads(agent_prompt(task)))
                self.assertNotIn('source_url', agent_prompt(task))
                self.assertNotIn('fix_id', agent_prompt(task))
                self.assertNotIn('changes', json.dumps([e['observation'] for e in record['trajectory'] if e['tool']=='list_repairs']))

    def test_cheaper_unsafe_action_is_genuine_new_outage(self):
        for task in TASKS:
            with self.subTest(task=task):
                case = source_case(task)
                base_down, _ = simulate(case)
                unsafe = next(a for a in case['actions'] if a['id']=='A90')
                best = reference_answer(case)
                optimal = next(a for a in case['actions'] if a['id']==best['fix_id'])
                after_down, _ = simulate(case, patch_facts(case['facts'], unsafe))
                self.assertTrue(after_down-base_down)
                self.assertLess(unsafe['cost'], optimal['cost'])
                self.assertEqual(best['root_cause'], next(x for x,_ in get_spec(task).hypotheses if x==best['root_cause']))
                self.assertEqual(set(service_codes(task)), {n['id'] for n in case['facts']['topology']})
                self.assertFalse(run_mock(task, unsafe=True)['grade']['strict_pass'])

    def test_wrong_cause_and_evidence_theater_fail(self):
        for task in TASKS:
            with self.subTest(task=task):
                wrong = run_mock(task, wrong_cause=True)
                self.assertFalse(wrong['grade']['strict_pass'])
                self.assertIn('root_cause_id_incorrect', wrong['grade']['strict_failure_reasons'])
                fabricated = run_mock(task, bogus_evidence=True)
                self.assertFalse(fabricated['grade']['strict_pass'])
                self.assertIn('insufficient_evidence_provenance', fabricated['grade']['strict_failure_reasons'])

    def test_forged_replay_fails_and_cannot_edit_history(self):
        record = run_mock('RW03V5')
        changed = deepcopy(record)
        changed['trajectory'][1]['observation']['result']['statuses']['svc-001'] = 'healthy'
        self.assertFalse(replay_record(changed)['verified'])
        self.assertEqual(record['grade']['score'], 1)

if __name__ == '__main__':
    unittest.main()
