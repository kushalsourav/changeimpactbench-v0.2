"""Every active task must have a reference snapshot accepted by dashboard audit."""
import json
import unittest
from pathlib import Path
from benchmarks.native_agent import GRAPH_BASE, source_case
from oracle import reference_answer
from dashboard_data import audit_record
from benchmarks.runner import run_episode
from tests_fake_graph_v4 import scripted_factory

ROOT = Path(__file__).resolve().parent.parent

class ReferencePresenceTests(unittest.TestCase):
    def test_each_active_scenario_has_exact_oracle_reference(self):
        for task, seed in GRAPH_BASE.items():
            with self.subTest(task=task):
                ref = ROOT / "reference" / (seed + ".json")
                self.assertTrue(ref.is_file(), f"Missing reference snapshot: {ref}")
                self.assertEqual(json.loads(ref.read_text()), reference_answer(source_case(task)))

    def test_six_task_v4_reference_episodes_are_dashboard_gradeable(self):
        for task in ("RW04V4", "RW05V4", "RW06V4"):
            with self.subTest(task=task):
                record = run_episode(task, "mock/reference:free", 1, "offline-key", 1024, "low", 0, 3, graph_factory=scripted_factory)
                audit = audit_record(record)
                self.assertEqual(audit["status"], "completed", audit["warnings"])
                self.assertTrue(audit["prompt_sha_matches"])
                self.assertTrue(audit["reference_matches"])
                self.assertTrue(audit["stored_grade_matches"])
                self.assertIsNotNone(audit["grade"])

if __name__ == "__main__":
    unittest.main()
