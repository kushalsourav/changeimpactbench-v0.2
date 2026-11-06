"""New frozen AG09--AG12 tool tasks: reference, safety, provenance, grading.

These are *mock provider* tests, not reported model performance.
"""
from __future__ import annotations

from copy import deepcopy
import json
import unittest

from agentic_suite import (TASK_IDS, SPECS, AgentEnvironment, agent_prompt,
                           implementation_hashes, reference_trajectory,
                           replay_record, source_case)
from oracle import reference_answer, reference_audit
from run_agentic_suite import run_episode


def fake_episode(task_id: str, authored=None):
    steps = list(authored if authored is not None else reference_trajectory(task_id))
    responses = [json.dumps({'tool': tool, 'arguments': args}) for tool, args in steps]
    offset = 0

    def request(_url, _key, _payload):
        nonlocal offset
        raw = responses[offset]
        offset += 1
        return {'id': f'mock-{task_id}-{offset}', 'model': 'mock/suite:free',
                'choices': [{'finish_reason': 'stop', 'message': {'content': raw}}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 50}}

    return run_episode(task_id, 'mock/suite:free', 1, 'offline-test-key',
                       2048, 'low', 0.0, 0.0, request)


class AgenticSuiteTests(unittest.TestCase):
    def test_all_four_cases_have_distinct_validated_references_and_frozen_prompts(self):
        self.assertEqual(len(TASK_IDS), 5)
        seen_versions = set()
        for task_id in sorted(TASK_IDS):
            with self.subTest(task_id=task_id):
                case = source_case(task_id)
                ref = reference_answer(case)
                audit = reference_audit(case)['actions']
                self.assertGreater(len(ref['failed_services']), 0)
                self.assertIn(ref['fix_id'], audit)
                optimum = min(action['cost'] for action in case['actions']
                              if audit[action['id']]['full_recovery'])
                chosen_cost = next(action['cost'] for action in case['actions']
                                   if action['id'] == ref['fix_id'])
                self.assertEqual(chosen_cost, optimum)
                self.assertEqual(audit[ref['fix_id']]['failed_after'], [])
                spec = SPECS[task_id]
                self.assertNotIn(spec['version'], seen_versions)
                seen_versions.add(spec['version'])
                prompt = agent_prompt(task_id)
                self.assertIn('LOWEST-COST', prompt)
                self.assertNotIn(json.dumps(ref['failed_services']), prompt)
                self.assertNotIn('"fix_id": "' + ref['fix_id'] + '"', prompt)
                self.assertLessEqual(len(reference_trajectory(task_id)), 23)

    def test_all_four_reference_agents_pass_independent_replay(self):
        for task_id in sorted(TASK_IDS):
            with self.subTest(task_id=task_id):
                record = fake_episode(task_id)
                self.assertEqual(record['status'], 'completed')
                self.assertTrue(record['replay_verified'])
                self.assertTrue(record['grade']['strict_pass'])
                self.assertEqual(record['grade']['score'], 1.0)
                self.assertEqual(record['grade']['committed_action'], reference_answer(source_case(task_id))['fix_id'])
                self.assertEqual(record['source_hashes'], implementation_hashes())

    def test_a_more_expensive_complete_repair_is_not_a_strict_pass(self):
        for task_id in sorted(TASK_IDS):
            case = source_case(task_id)
            correct = reference_answer(case)['fix_id']
            actions = reference_audit(case)['actions']
            candidates = [a for a in case['actions']
                          if actions[a['id']]['full_recovery'] and a['id'] != correct]
            self.assertTrue(candidates)
            costlier = max(candidates, key=lambda a:a['cost'])['id']
            authored = []
            for tool, args in reference_trajectory(task_id):
                args = deepcopy(args)
                if tool == 'apply_repair':
                    args['action_id'] = costlier
                if tool == 'submit_diagnosis':
                    args['fix_id'] = costlier
                authored.append((tool, args))
            record = fake_episode(task_id, authored)
            with self.subTest(task_id=task_id):
                self.assertTrue(record['replay_verified'])
                self.assertFalse(record['grade']['strict_pass'])
                self.assertFalse(record['grade']['fix_correct'])
                self.assertTrue(record['grade']['recovery_success'])
                self.assertTrue(record['grade']['recovery_safe'])

    def test_incomplete_repair_is_not_a_strict_pass(self):
        for task_id in sorted(TASK_IDS):
            case = source_case(task_id)
            audit = reference_audit(case)['actions']
            partial = next(a['id'] for a in case['actions'] if not audit[a['id']]['full_recovery'])
            authored = []
            for tool, args in reference_trajectory(task_id):
                args = deepcopy(args)
                if tool == 'apply_repair':
                    args['action_id'] = partial
                if tool == 'submit_diagnosis':
                    args['fix_id'] = partial
                authored.append((tool, args))
            record = fake_episode(task_id, authored)
            with self.subTest(task_id=task_id):
                self.assertTrue(record['replay_verified'])
                self.assertFalse(record['grade']['strict_pass'])
                self.assertFalse(record['grade']['recovery_success'])

    def test_raw_output_tampering_disables_grading(self):
        record = fake_episode('AG09')
        altered = deepcopy(record)
        altered['turns'][0]['raw_model_output'] = '{"tool":"list_repairs","arguments":{}}'
        self.assertFalse(replay_record(altered)['verified'])
        self.assertIsNone(replay_record(altered)['grade'])
        altered = deepcopy(record)
        altered['trajectory'][1]['observation']['result']['configured_local_check'] = False
        self.assertFalse(replay_record(altered)['verified'])

    def test_reference_alert_and_tool_view_do_not_include_oracle_answer(self):
        for task_id in sorted(TASK_IDS):
            environment = AgentEnvironment(task_id)
            alert = environment.execute('read_alert', {})['result']
            ref = reference_answer(source_case(task_id))
            self.assertNotIn('failed_services', alert)
            self.assertNotIn('fix_id', alert)
            self.assertEqual(len(alert['hypotheses']),5)
            self.assertNotIn(ref['fix_id'], json.dumps(alert))


if __name__ == '__main__':
    unittest.main()
