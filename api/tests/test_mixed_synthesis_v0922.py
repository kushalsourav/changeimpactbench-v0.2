"""Regression tests: mixed verified/unverified batches preserve raw evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from api.routes import synthesis
from api.tests.test_research_reporting_v0921 import record, audit, legacy_summary


class TestMixedResearch(unittest.TestCase):
    def test_zero_based_indices_not_renumbered(self):
        rows = [{'episode': 0, 'gradeable': False},
                {'episode': 1, 'gradeable': True},
                {'episode': 2, 'gradeable': False}]
        facts = {'episodes': rows}
        self.assertTrue(synthesis.valid_supporting_episodes([1], facts))
        self.assertFalse(synthesis.valid_supporting_episodes([0], facts))
        self.assertFalse(synthesis.valid_supporting_episodes([2], facts))
        self.assertFalse(synthesis.valid_supporting_episodes([3], facts))
        self.assertFalse(synthesis.valid_supporting_episodes([], facts))

    def test_payload_only_includes_gradeable_details(self):
        facts = {'episodes': [{'episode': 0, 'gradeable': False, 'task': 'RW05V4',
                               'model': 'nvidia', 'status': 'unverified',
                               'error_category': 'multiple_native_tools_in_provider_response',
                               'partial_score': None, 'committed_action': None},
                              {'episode': 1, 'gradeable': True, 'task': 'RW05V4',
                               'model': 'nano', 'status': 'completed', 'error_category': None,
                               'strict_pass': False, 'partial_score': .85}],
                 'origin': 'synthetic', 'replay': 'deterministic'}
        payload = synthesis.research_payload(facts)
        self.assertEqual(payload['gradeable_episode_ids'], [1])
        self.assertEqual(payload['strict_failures'], 1)
        self.assertEqual(payload['non_gradeable_episodes_status_only'][0]['episode'], 0)
        self.assertNotIn('committed_action', payload['non_gradeable_episodes_status_only'][0])

    def test_multi_tool_replay_mismatch_is_not_scored(self):
        r = record()
        r['status'] = 'unverified'
        r['turns'] = [{'turn': 1, 'tool_calls': [{'name': 'read_alert'}, {'name': 'scan_service_health'}]}]
        r['audit_warnings'] = ['Recorded graph tool attempts differ from sandbox replay']
        a = audit()
        a['status'] = 'unverified'
        a['grade'] = None
        with patch.object(synthesis, 'audit_record', return_value=a):
            item = synthesis.facts_for([r])['episodes'][0]
        self.assertFalse(item['gradeable'])
        self.assertIsNone(item['strict_pass'])
        self.assertIsNone(item['partial_score'])
        self.assertEqual(item['error_category'], 'multiple_native_tools_in_provider_response')
        self.assertEqual(item['multi_tool_provider_turns'], [1])

    def test_invalid_gemini_citation_fallback_keeps_verifier_facts(self):
        rows = [{'episode': 0, 'gradeable': False, 'model': 'nvidia', 'status': 'unverified',
                 'strict_pass': None, 'recovery_success': None, 'recovery_safe': None},
                {'episode': 1, 'gradeable': True, 'model': 'nano', 'status': 'completed',
                 'strict_pass': False, 'recovery_success': True, 'recovery_safe': True,
                 'impact_f1': 1.0, 'root_correct': True, 'unsafe_commit': False,
                 'protocol_errors': 2, 'strict_failure_reasons': ['repair_not_reference_optimal'],
                 'partial_score': .85}]
        facts = {'episodes': rows, 'source_postmortems': [], 'origin': 'synthetic', 'replay': 'deterministic'}
        with patch.object(synthesis, 'run_manifest', return_value={'experiment_id': 'c687f27f4709'}):
            result = synthesis.verified_fallback('ui_c687f27f4709.jsonl', [{}, {}], facts, 'gemini', ['Invalid citation'])
        self.assertFalse(result['available'])
        self.assertIsNone(result['synthesis'])
        self.assertEqual(result['verified_facts']['strict_failures'], 1)
        self.assertEqual(result['verified_facts']['ungradeable_count'], 1)
        self.assertEqual(result['experiment_id'], 'c687f27f4709')
        self.assertEqual(result['chart']['rows'][4]['label'], 'Non-optimal repair')
        self.assertEqual(result['chart']['rows'][4]['value'], 1)

if __name__ == '__main__':
    unittest.main()
