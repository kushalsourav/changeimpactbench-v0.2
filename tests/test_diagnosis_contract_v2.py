"""Prospective root-cause classification contract, regression from real RW01 v1.

Mocks only the provider: every grading assertion is real deterministic replay.
The existing v1 score must NEVER be rewritten by this test or migration.
"""
from __future__ import annotations
from copy import deepcopy
from types import SimpleNamespace
import json
import unittest
from benchmarks.spec import reference_trajectory
from benchmarks.native_agent import GraphEnvironment, agent_prompt, TASK_IDS
from benchmarks.grader import replay_record
from run_graph_agent import run_episode


class SyntheticGraph:
    def __init__(self, env, *, wrong_id=False, excess_simulation=False):
        self.env = env
        self.wrong_id = wrong_id
        self.excess_simulation = excess_simulation

    def stream(self, _prompt, config, stream_mode):
        steps = list(reference_trajectory(self.env.task_id))
        if self.wrong_id:
            name, final = steps[-1]
            steps[-1] = (name, {**final, 'root_cause_id': 'H01'})
        if self.excess_simulation:
            insertion = next(i for i, (tool, _) in enumerate(steps) if tool == 'apply_repair')
            # Two simulations in the reference; third is allowed, fourth rejected.
            repair = steps[insertion - 1][1]
            steps[insertion:insertion] = [('simulate_repair', repair), ('simulate_repair', repair)]
        for index, (name, args) in enumerate(steps, 1):
            uid = f'offline-v2-{index}'
            yield {'model': {'messages': [SimpleNamespace(type='ai', content='',
                tool_calls=[{'name': name, 'args': args, 'id': uid}],
                usage_metadata={}, response_metadata={}, additional_kwargs={}, id=uid)]}}
            obs = self.env.execute(name, args, uid)
            yield {'tools': {'messages': [SimpleNamespace(type='tool', content=obs)]}}


def run_case(task='RW01V3', **options):
    return run_episode(task, 'mock/contract-v2:free', 1, 'offline-test-key',
        2048, 'low', 0, 3, graph_factory=lambda env, *_: SyntheticGraph(env, **options))


class DiagnosisContractTests(unittest.TestCase):
    def test_all_new_prompts_explicitly_require_id_and_explanation(self):
        self.assertTrue({'RW01V3', 'RW02V3', 'RW03V3'}.issubset(TASK_IDS))
        for case in sorted(t for t in TASK_IDS if t.endswith('V3')):
            prompt = json.loads(agent_prompt(case))
            self.assertIn('root_cause_id', prompt['diagnosis_contract'])
            self.assertIn('root_cause_explanation', prompt['diagnosis_contract'])
            self.assertEqual(len(prompt['hypotheses']), 5)
            self.assertNotIn('facts', prompt)

    def test_rejects_free_form_prose_in_id_field(self):
        env = GraphEnvironment('RW01V3')
        steps = reference_trajectory('RW01V3')
        for i, (name, args) in enumerate(steps[:-1], 1):
            env.provider_turn = i
            self.assertNotIn('rejected', json.loads(env.execute(name, args, str(i))))
        _, submission = steps[-1]
        env.provider_turn = len(steps)
        invalid = {**submission, 'root_cause_id': submission['root_cause_explanation']}
        rejection = json.loads(env.execute('submit_diagnosis', invalid, 'bad'))
        self.assertTrue(rejection['rejected'])
        self.assertIsNone(env.final)
        self.assertEqual(len(env.attempts), len(steps))
        self.assertIn('Invalid final diagnosis', rejection['reason'])

    def test_correct_id_with_custom_causal_explanation_is_correct(self):
        for task in sorted(t for t in TASK_IDS if t.endswith('V3')):
            with self.subTest(task=task):
                record = run_case(task)
                self.assertTrue(record['replay_verified'])
                self.assertTrue(record['grade']['strict_pass'])
                self.assertEqual(record['grade']['root_cause_id_submitted'], record['grade']['root_cause_id_expected'])
                self.assertEqual(record['grade']['criterion_scores']['root_cause_id']['earned'], 20)
                self.assertIn('human semantic review', record['grade']['root_cause_explanation_review'])
                self.assertEqual(record['grade']['strict_failure_reasons'], [])
                self.assertEqual(sum(c['earned'] for c in record['grade']['criterion_scores'].values()), 100)

    def test_wrong_id_is_diagnosis_error_not_protocol_error(self):
        record = run_case(wrong_id=True)
        grade = record['grade']
        self.assertTrue(record['replay_verified'])
        self.assertEqual(grade['score'], .80)
        self.assertFalse(grade['root_correct'])
        self.assertEqual(grade['strict_failure_reasons'], ['root_cause_id_incorrect'])
        self.assertEqual(grade['protocol_errors'], [])
        self.assertTrue(grade['recovery_success'])
        self.assertTrue(grade['recovery_safe'])

    def test_fourth_simulation_is_protocol_error_not_diagnosis_error(self):
        record = run_case(excess_simulation=True)
        grade = record['grade']
        self.assertTrue(record['replay_verified'])
        self.assertEqual(grade['score'], .95)
        self.assertTrue(grade['root_correct'])
        self.assertTrue(grade['fix_correct'])
        self.assertTrue(grade['recovery_safe'])
        self.assertTrue(grade['recovery_success'])
        self.assertEqual(grade['criterion_scores']['protocol_discipline']['earned'], 5)
        self.assertEqual(grade['strict_failure_reasons'], ['rejected_tool_attempts'])
        self.assertEqual(len(grade['protocol_errors']), 1)
        self.assertFalse(grade['strict_pass'])
        self.assertEqual(sum(c['earned'] for c in grade['criterion_scores'].values()), 95)

    def test_replay_detects_tampered_root_id(self):
        record = run_case()
        tampered = deepcopy(record)
        tampered['final_diagnosis']['root_cause_id'] = 'H01'
        self.assertFalse(replay_record(tampered)['verified'])
        self.assertTrue(record['replay_verified'])

if __name__ == '__main__':
    unittest.main()
