"""v0.9.21 Research Lab regression tests; offline and provider-free."""
from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from api.routes import synthesis


def record(task='RW05V4'):
    # The fake audit below deliberately contains no model-specific UI override.
    return {'task_id': task, 'model_requested': 'example/independent-model:free',
            'trial': 1, 'status': 'completed', 'protocol_errors': [], 'tool_calls': 14,
            'provider_requests': 14}


def audit(*, strict=False, repair='A04', score=.95, protocol_errors=1):
    return {
        'status': 'completed', 'prompt_sha_matches': True,
        'reference_matches': True, 'stored_grade_matches': True,
        'grade': {
            'strict_pass': strict, 'score': score, 'committed_action': repair,
            'affected_f1': 1.0, 'root_correct': True, 'root_cause_id_submitted': 'H03',
            'root_cause_id_expected': 'H03', 'recovery_success': True,
            'recovery_safe': True, 'unsafe_commit': False,
            'strict_failure_reasons': [] if strict else ['repair_not_reference_optimal'],
            'criterion_scores': {'safe_complete_recovery': {'earned': 40}},
            'protocol_errors': [{'turn': 10}] * protocol_errors,
        },
    }


def legacy_summary(text):
    return synthesis.ResearchSynthesis(
        headline='Automated infrastructure investigation results',
        interpretation=text,
        observations=['Complete recovery was achieved and the diagnosis ID was correct.'],
        limitations='One reconstructed incident; not a population-level estimate.',
        chart_choice='outcome_rates', chart_explanation='Model strict pass percentages.',
        supporting_episodes=[0],
    )


class ResearchReportingV0921Tests(unittest.TestCase):
    def test_costs_and_strict_failure_come_from_verifier_not_model_identity(self):
        with patch.object(synthesis, 'audit_record', return_value=audit()):
            item = synthesis.facts_for([record('RW05V4')])['episodes'][0]
        self.assertTrue(item['gradeable'])
        self.assertIs(item['strict_pass'], False)
        self.assertEqual(item['partial_score'], .95)
        self.assertEqual(item['committed_action'], 'A04')
        self.assertEqual(item['committed_cost'], 7)
        self.assertEqual(item['reference_optimal_action'], 'A03')
        self.assertEqual(item['reference_optimal_cost'], 5)
        self.assertEqual(item['repair_cost_delta'], 2)
        self.assertTrue(item['recovery_safe'])
        self.assertTrue(item['recovery_success'])
        self.assertEqual(synthesis.verifier_summary({'episodes': [item]})['strict_failures'], 1)

    def test_rw06_cost_and_rw04_pass_are_driven_by_task_fixture(self):
        with patch.object(synthesis, 'audit_record', return_value=audit()):
            kv = synthesis.facts_for([record('RW06V4')])['episodes'][0]
        self.assertEqual((kv['committed_cost'], kv['reference_optimal_action'], kv['reference_optimal_cost']),
                         (7, 'A02', 3))
        with patch.object(synthesis, 'audit_record', return_value=audit(strict=True,repair='A02',score=.95)):
            route = synthesis.facts_for([record('RW04V4')])['episodes'][0]
        self.assertTrue(route['strict_pass'])
        self.assertEqual(route['repair_cost_delta'], 0)

    def test_unverified_records_are_not_falsely_assigned_scores(self):
        broken = audit()
        broken['stored_grade_matches'] = False
        with patch.object(synthesis, 'audit_record', return_value=broken):
            item = synthesis.facts_for([record()])['episodes'][0]
        self.assertFalse(item['gradeable'])
        self.assertIsNone(item['strict_pass'])
        self.assertIsNone(item['partial_score'])
        self.assertIsNone(item['committed_cost'])

    def test_experiment_identity_comes_from_manifest_even_if_episode_has_none(self):
        with patch.object(synthesis, 'run_manifest', return_value={
            'output_file': 'ui_test.jsonl', 'experiment_id': 'observed12abc'
        }):
            self.assertEqual(synthesis._experiment_identity('ui_test.jsonl', [record()]),
                             ('observed12abc', 'run_manifest'))
        with patch.object(synthesis, 'run_manifest', return_value=None):
            self.assertEqual(synthesis._experiment_identity('ui_test.jsonl', [record()]),
                             (None, 'unavailable'))

    def test_llm_must_explicitly_distinguish_strict_fail_and_cost(self):
        with patch.object(synthesis, 'audit_record', return_value=audit()):
            facts = synthesis.facts_for([record()])
        self.assertEqual(len(synthesis._narrative_checks(legacy_summary(
            'Safe and complete recovery with correct root cause was achieved during the incident response.'), facts)), 2)
        acceptable = legacy_summary(
            'The model safely restored all services, but the strict verdict was FAIL due to a non-optimal repair. '
            'It committed A04 at cost 7 instead of reference A03 at cost 5.')
        self.assertEqual(synthesis._narrative_checks(acceptable, facts), [])

    def test_cached_legacy_prose_is_suppressed_and_cached_chart_is_recomputed(self):
        episode = record()
        with tempfile.TemporaryDirectory() as directory:
            cached = {
                'available': True, 'record_sha256': synthesis._fingerprint([episode]),
                'experiment_id': None, 'synthesis': legacy_summary(
                    'Safe and complete recovery with correct root cause was achieved during the incident response.').model_dump(),
                'chart': {'type': 'outcome_rates', 'rows': [{'label': 'fabricated', 'value': 100, 'denominator': 1}]},
            }
            Path(directory, 'ui_test.synthesis.json').write_text(json.dumps(cached))
            with patch.object(synthesis, 'RESULTS', Path(directory)), \
                 patch.object(synthesis, 'records_for', return_value=[episode]), \
                 patch.object(synthesis, 'audit_record', return_value=audit()), \
                 patch.object(synthesis, 'run_manifest', return_value={'experiment_id':'manifest-result'}):
                result = synthesis.get_synthesis('ui_test.jsonl')
        self.assertEqual(result['experiment_id'], 'manifest-result')
        self.assertEqual(result['verified_facts']['strict_failures'], 1)
        self.assertEqual(result['narrative_validation']['status'], 'blocked_inconsistent')
        self.assertIsNone(result['synthesis'])
        self.assertEqual(result['chart']['rows'][0]['value'], 0)

    def test_without_llm_sidecar_verifier_facts_still_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(synthesis, 'RESULTS', Path(directory)), \
                 patch.object(synthesis, 'records_for', return_value=[record()]), \
                 patch.object(synthesis, 'audit_record', return_value=audit()), \
                 patch.object(synthesis, 'run_manifest', return_value={'experiment_id':'manifest-result'}):
                result = synthesis.get_synthesis('ui_test.jsonl')
        self.assertFalse(result['available'])
        self.assertEqual(result['experiment_id'], 'manifest-result')
        self.assertEqual(result['verified_facts']['complete_safe_recoveries'], 1)
        self.assertEqual(result['verified_facts']['strict_passes'], 0)


if __name__ == '__main__':
    unittest.main()
