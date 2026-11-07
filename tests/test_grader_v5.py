"""Offline regression tests for additive V5 evidence-category audit."""
from __future__ import annotations
from copy import deepcopy
import unittest
from benchmarks.grader_v5 import QUALIFYING_TOOLS, audit_v5
from benchmarks.runner import run_episode
from tests_fake_graph_v4 import scripted_factory


def sample(task='RW02V4', **opts):
    return run_episode(task, 'mock/v5:offline', 1, 'offline-test-token',
                       1024, 'low', 0, 3,
                       graph_factory=lambda env,*_: scripted_factory(env, **opts))


class GraderV5Tests(unittest.TestCase):
    def test_dependencies_are_qualifying_support(self):
        self.assertIn('inspect_dependencies', QUALIFYING_TOOLS)

    def test_reproduces_rw02_dependency_heavy_evidence_failure_without_rewriting_v4(self):
        record = sample()
        baseline = deepcopy(record['grade'])
        # Citation selection mirrors the actual RW02 model: one config + seven dependencies.
        evidence = [x['observation']['event_id'] for x in record['trajectory']
                    if x['tool'] == 'inspect_dependencies'][:7]
        evidence.insert(0, next(x['observation']['event_id'] for x in record['trajectory']
                                if x['tool'] == 'inspect_config'))
        # Modify the actual model's terminal native arguments, not a cached grade.
        submission = next(x for x in record['turns'][-1]['tool_calls']
                          if x['name'] == 'submit_diagnosis')
        submission['args']['evidence_ids'] = evidence
        # Also align record's submitted diagnosis and cached accepted observations:
        # independently replaying this should still require canonical record fields.
        record['final_diagnosis']['evidence_ids'] = evidence
        record['tool_attempts'][-1]['arguments']['evidence_ids'] = evidence
        record['trajectory'][-1]['arguments']['evidence_ids'] = evidence
        # The validated handoff was authored earlier; only terminal submission changed.
        record['raw_output'] = ''  # raw output not verified as part of replay
        audit = audit_v5(record)
        self.assertTrue(audit['verified'], audit['warnings'])
        self.assertEqual(audit['historical_v4_grade']['evidence_score'], 5)
        self.assertEqual(audit['grade']['evidence_score'], 10)
        self.assertTrue(audit['grade']['strict_pass'])
        self.assertEqual(record['grade'], baseline)  # no mutation of saved historical grade

    def test_reference_v4_runs_preserve_success(self):
        for task in ('RW01V4', 'RW02V4', 'RW03V4'):
            with self.subTest(task=task):
                audit = audit_v5(sample(task))
                self.assertTrue(audit['verified'], audit['warnings'])
                self.assertTrue(audit['grade']['strict_pass'])
                self.assertEqual(audit['grade']['evidence_score'], 10)

    def test_premature_simulation_remains_procedural_penalty_not_strict_failure(self):
        audit = audit_v5(sample('RW01V4', premature=True))
        self.assertTrue(audit['grade']['strict_pass'])
        self.assertEqual(audit['grade']['procedure_score'], 5)
        self.assertEqual(audit['grade']['score'], .95)

    def test_incomplete_repair_still_fails(self):
        audit = audit_v5(sample('RW01V4', wrong_fix=True))
        self.assertTrue(audit['verified'])
        self.assertFalse(audit['grade']['strict_pass'])
        self.assertIn('incomplete_recovery', audit['grade']['strict_failure_reasons'])

    def test_invented_citation_is_not_accepted(self):
        record = sample()
        record['turns'][-1]['tool_calls'][0]['args']['evidence_ids'].append('EV999')
        # Tampering without corresponding sandbox replay fields fails independent verification.
        audit = audit_v5(record)
        self.assertFalse(audit['verified'])
        self.assertIsNone(audit['grade'])

    def test_source_hash_tampering_is_rejected(self):
        record = sample()
        record['source_hashes']['benchmarks/grader.py'] = '0' * 64
        self.assertFalse(audit_v5(record)['verified'])


if __name__ == '__main__':
    unittest.main()
