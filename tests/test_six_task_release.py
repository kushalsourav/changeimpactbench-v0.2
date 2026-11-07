"""Offline-only independent replay; model comparisons require actual provider trials."""
from __future__ import annotations
import unittest
from oracle import simulate, reference_answer, reference_audit, patch_facts
from benchmarks.spec import source_case, reference_trajectory
from benchmarks.runner import run_episode
from tests_fake_graph_v4 import scripted_factory
from benchmarks.grader import replay_record

TASKS = ('RW04V4','RW05V4','RW06V4')

class SixTaskReleaseTests(unittest.TestCase):
    def test_independent_correct_answers_and_decoys(self):
        expected = {'RW04V4':('H02','A02',7),'RW05V4':('H03','A03',8),'RW06V4':('H01','A02',7)}
        for task in TASKS:
            with self.subTest(task=task):
                case=source_case(task)
                ref=reference_answer(case)
                self.assertEqual((ref['root_cause'],ref['fix_id'],len(ref['failed_services'])),expected[task])
                audit=reference_audit(case)['actions']
                self.assertTrue(audit[ref['fix_id']]['full_recovery'])
                self.assertFalse(audit['A01']['full_recovery'])
                self.assertEqual(len(ref['failed_services']),len(set(ref['failed_services'])))
                self.assertEqual(len(case['facts']['topology']),10)
                self.assertTrue(case['provenance']['measurement_note'].endswith('NOT production measurements.'))
    def test_real_native_tools_offline_scripted_reference(self):
        for task in TASKS:
            with self.subTest(task=task):
                record=run_episode(task,'mock/reference:free',1,'offline-key',1024,'low',0,3,graph_factory=scripted_factory)
                self.assertEqual(record['status'],'completed')
                self.assertTrue(record['replay_verified'])
                self.assertTrue(record['grade']['strict_pass'])
                self.assertLess(record['provider_requests'],48)
    def test_rw03_safe_but_costly_is_strict_failure(self):
        case=source_case('RW03V4'); ref=reference_answer(case)
        self.assertEqual(ref['fix_id'],'A02')
        expensive=next(x for x in case['actions'] if x['id']=='A04')
        down,_=simulate(case,patch_facts(case['facts'],expensive))
        self.assertFalse(down)
        self.assertGreater(expensive['cost'],next(x['cost'] for x in case['actions'] if x['id']=='A02'))
        # Safe complete does not imply reference-optimal or strict pass.
    def test_rw06_cheap_fail_open_breaks_healthy_security_policy(self):
        case=source_case('RW06V4')
        before,_=simulate(case)
        cheap=next(x for x in case['actions'] if x['id']=='A01')
        after,_=simulate(case,patch_facts(case['facts'],cheap))
        self.assertNotIn('security-policy',before)
        self.assertIn('security-policy',after)
        self.assertFalse(after & before)
        safe=next(x for x in case['actions'] if x['id']=='A02')
        self.assertEqual(simulate(case,patch_facts(case['facts'],safe))[0],set())

if __name__=='__main__':unittest.main()

class FrozenHistoryCompatibilityTests(unittest.TestCase):
    def test_legacy_v019_hash_manifest_pinned_and_archive_untampered(self):
        import json
        from pathlib import Path
        from benchmarks.native_agent import recorded_implementation_hashes, implementation_hashes
        archive=Path(__file__).resolve().parent.parent/'legacy/v0.9.19/source_hashes.json'
        old=json.loads(archive.read_text())
        self.assertEqual(recorded_implementation_hashes('RW03V4',old),old)
        self.assertEqual(recorded_implementation_hashes('RW01V4',old),old)
        self.assertEqual(recorded_implementation_hashes('RW02V4',old),old)
        self.assertEqual(recorded_implementation_hashes('RW04V4',old),implementation_hashes())
