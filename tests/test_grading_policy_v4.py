"""New historical V4 scoring must not reuse the synthetic strict verdict."""
import unittest
from unittest.mock import patch
from benchmarks.grading_policy import contract_for, replay_record, SOURCE_CONTRACT


class SourceRoutingTests(unittest.TestCase):
    def setUp(self):
        self.base = {'verified': True, 'warnings': [], 'grade': {'strict_pass': True, 'score': 1.0, 'committed_action': 'A02'},
                     'expected': {'failed_services': []}, 'predicted': {'root_cause_explanation': 'The WAF regex caused CPU saturation', 'rationale': 'Rollback the WAF rule'}}

    def test_six_originals_use_source_contract(self):
        for i in range(1, 7):
            self.assertEqual(contract_for(f'RW{i:02d}V4'), SOURCE_CONTRACT)
            self.assertEqual(contract_for(f'RW{i:02d}V6CF'), 'synthetic-replay')

    def test_historical_score_never_invents_strict_pass(self):
        with patch('benchmarks.grading_policy.replay_sandbox', return_value=self.base):
            grade = replay_record({'task_id': 'RW03V4', 'status': 'completed', 'grading_contract': SOURCE_CONTRACT})['grade']
        self.assertTrue(grade['source_provisional'])
        self.assertIsNone(grade['strict_pass'])
        self.assertIsNone(grade['recovery_success'])
        self.assertEqual(grade['grading_contract'], SOURCE_CONTRACT)
        self.assertTrue(0 <= grade['score'] <= 1)

    def test_counterfactual_and_old_records_preserve_existing_grades(self):
        with patch('benchmarks.grading_policy.replay_sandbox', return_value=self.base):
            for record in ({'task_id': 'RW03V6CF'}, {'task_id': 'RW03V4'}):
                self.assertIs(replay_record(record)['grade'], self.base['grade'])

    def test_incomplete_v4_ungraded(self):
        with patch('benchmarks.grading_policy.replay_sandbox', return_value=self.base):
            actual = replay_record({'task_id': 'RW03V4', 'status': 'budget_exhausted', 'grading_contract': SOURCE_CONTRACT})
        self.assertIsNone(actual['grade'])


if __name__ == '__main__':
    unittest.main()
