"""A strict evaluation must not confuse safe recovery with complete reporting."""
from benchmarks.grader import replay_record as _legacy_replay
import unittest
from benchmarks.runner import run_episode
from benchmarks.grader_v5 import audit_v5
from tests_fake_graph_v4 import scripted_factory


class LightningInventoryRegression(unittest.TestCase):
    def test_omitting_pull_request_metadata_fails_even_with_full_recovery(self):
        rec = run_episode('RW01V4', 'offline/inventory-fixture', 1, 'fixture',
                          1024, 'low', 0, 3,
                          graph_factory=lambda env, *_: scripted_factory(env))
        self.assertTrue(_legacy_replay(rec)['grade']['strict_pass'])
        self.assertEqual(len(rec['committed_effect']['restored']), 9)
        omitted = 'pull-request-metadata'
        for tool in ('prepare_repair', 'submit_diagnosis'):
            attempt = next(x for x in rec['tool_attempts'] if x['tool'] == tool)
            self.assertIn(omitted, attempt['arguments']['failed_services'])
            attempt['arguments']['failed_services'] = [x for x in attempt['arguments']['failed_services'] if x != omitted]
            item = next(x for x in rec['trajectory'] if x['tool'] == tool)
            item['arguments']['failed_services'] = [x for x in item['arguments']['failed_services'] if x != omitted]
            turn = next(t for t in rec['turns'] if any(c['name'] == tool for c in t['tool_calls']))
            call = next(c for c in turn['tool_calls'] if c['name'] == tool)
            call['args']['failed_services'] = [x for x in call['args']['failed_services'] if x != omitted]
        rec['repair_brief']['failed_services'] = [x for x in rec['repair_brief']['failed_services'] if x != omitted]
        rec['final_diagnosis']['failed_services'] = [x for x in rec['final_diagnosis']['failed_services'] if x != omitted]
        # The recorded repair-phase system prompt is derived from the handoff;
        # regenerate it to reflect the altered, consistently model-authored brief.
        import hashlib
        from benchmarks.skills import repair_system_prompt
        from benchmarks.native_agent import agent_prompt
        rec['repair_system_prompt'] = repair_system_prompt(agent_prompt('RW01V4'), rec['repair_brief'])
        rec['repair_system_prompt_sha256'] = hashlib.sha256(rec['repair_system_prompt'].encode()).hexdigest()
        audited = audit_v5(rec)
        self.assertTrue(audited['verified'], audited['warnings'])
        score = audited['grade']
        self.assertTrue(score['recovery_success'])
        self.assertTrue(score['recovery_safe'])
        self.assertFalse(score['strict_pass'])
        self.assertIn('initial_service_inventory_inexact', score['strict_failure_reasons'])
        self.assertAlmostEqual(score['affected_f1'], 16/17, places=5)


if __name__ == '__main__':
    unittest.main()
