"""Offline validation for dashboard evidence. No Streamlit install or internet required."""

import json
import sys
from hashlib import sha256
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dashboard_data import (
    parse_jsonl,
    evidence_rows,
    summary_rows,
    audit_record,
    case_diagnostics,
    topology_dot,
    repair_state,
    expected_trials_from_records,
)
from oracle import reference_answer, reference_audit
from tasks import load_cases, make_prompt


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = {c["id"]: c for c in load_cases()}
        cls.case = cls.cases["T01"]

    def record(self, **changes):
        case = self.case
        base = {
            "task_id": case["id"],
            "model_requested": "a/model:free",
            "model_returned": "a/model:free",
            "trial": 1,
            "status": "completed",
            "finish_reason": "stop",
            "prompt": make_prompt(case),
            "prompt_sha256": sha256(make_prompt(case).encode()).hexdigest(),
            "raw_output": json.dumps(reference_answer(case)),
            "grade": {
                "pass": True,
                "score": 1.0,
                "format_valid": True,
                "affected_f1": 1.0,
                "root_correct": True,
                "fix_correct": True,
            },
        }
        base.update(changes)
        return base

    def test_jsonl_parsing_and_bad_rows(self):
        rec = self.record()
        self.assertEqual(len(parse_jsonl(json.dumps(rec) + "\n")), 1)
        with self.assertRaises(ValueError):
            parse_jsonl('{"task_id": 5}\n')
        with self.assertRaises(ValueError):
            parse_jsonl("{broken}")

    def test_original_response_and_grade_verified(self):
        result = audit_record(self.record(), self.cases)
        self.assertTrue(result["prompt_sha_matches"])
        self.assertTrue(result["reference_matches"])
        self.assertTrue(result["stored_grade_matches"])
        self.assertTrue(result["grade"]["pass"])
        self.assertEqual(result["warnings"], [])

    def test_tampered_prompt_detected(self):
        r = self.record(prompt_sha256="bad_sha")
        result = audit_record(r, self.cases)
        self.assertFalse(result["prompt_sha_matches"])
        self.assertTrue(any("prompt" in x.lower() for x in result["warnings"]))
        # Incorrectly matched version must not be in reported accuracy.
        sr = summary_rows([r], 1)[0]
        self.assertEqual(sr["completed"], 0)
        self.assertEqual(sr["unverified"], 1)

    def test_tampered_stored_grade_detected_and_recomputed(self):
        r = self.record(grade={"pass": False, "score": 0.0})
        result = audit_record(r, self.cases)
        self.assertFalse(result["stored_grade_matches"])
        sr = summary_rows([r], 1)[0]
        self.assertEqual(sr["passed"], 1)
        self.assertEqual(sr["completed"], 1)

    def test_incomplete_old_generation_excluded(self):
        r = self.record(finish_reason="length", raw_output="", grade={"pass": False, "score": 0.0})
        result = audit_record(r, self.cases)
        self.assertEqual(result["status"], "incomplete_generation")
        self.assertIsNone(result["grade"])
        sr = summary_rows([r], 1)[0]
        self.assertEqual(sr["incomplete"], 1)
        self.assertIsNone(sr["exact_pass_rate"])

    def test_api_error_not_graded(self):
        r = self.record(status="api_error", raw_output="", grade=None, error="429")
        result = audit_record(r, self.cases)
        self.assertIsNone(result["grade"])
        sr = summary_rows([r], 1)[0]
        self.assertEqual(sr["api_errors"], 1)
        self.assertIsNone(sr["exact_pass_rate"])

    def test_missed_services_and_root_id(self):
        correct = reference_answer(self.case)
        wrong = {
            "failed_services": correct["failed_services"][:-1],
            "root_cause": "H01",
            "fix_id": correct["fix_id"],
        }
        d = case_diagnostics(self.record(raw_output=json.dumps(wrong)), self.case)
        self.assertTrue(d["can_parse"])
        self.assertEqual(d["missed_services"], [correct["failed_services"][-1]])
        self.assertEqual(d["extra_services"], [])
        self.assertFalse(d["grade"]["root_correct"])

    def test_graph_includes_dependency_edges_and_colors(self):
        expected = reference_answer(self.case)
        dot = topology_dot(self.case, set(expected["failed_services"]))
        self.assertIn("digraph services", dot)
        self.assertIn('label="ALL"', dot)
        self.assertIn("fee2e2", dot)
        self.assertIn("dcfce7", dot)
        self.assertIn('"policy-eu"', dot)

    def test_counterfactuals_match_oracle(self):
        for case in self.cases.values():
            audit = reference_audit(case)
            for action in case["actions"]:
                after = repair_state(case, action["id"])
                self.assertEqual(after, set(audit["actions"][action["id"]]["failed_after"]))

    def test_summary_k_completeness(self):
        records = [self.record(trial=1), self.record(trial=2)]
        self.assertEqual(expected_trials_from_records(records), 2)
        summary = summary_rows(records, 3)[0]
        self.assertEqual(summary["completed"], 2)
        self.assertIsNone(summary["pass_power_k"])
        self.assertEqual(summary["full_trial_groups"], 0)

    def test_evidence_rows_safe_for_missing_usage(self):
        row = evidence_rows([self.record()], self.cases)[0]
        self.assertIsNone(row["prompt_tokens"])
        self.assertTrue(row["pass"])
        self.assertEqual(row["warnings"], "")


class EvidenceIntegrityRegressionTests(unittest.TestCase):
    """Invalid or unknown evidence must not appear as a model success."""

    def test_tampered_hash_is_unverified_in_both_views(self):
        case = load_cases({"T01"})[0]
        raw = json.dumps(reference_answer(case))
        record = {
            "task_id": "T01",
            "model_requested": "test/mock:free",
            "trial": 1,
            "status": "completed",
            "raw_output": raw,
            "prompt_sha256": "deliberately-wrong-hash",
        }
        row = evidence_rows([record], {"T01": case})[0]
        self.assertEqual(row["status"], "unverified")
        self.assertIsNone(row["pass"])
        self.assertIsNone(row["score"])
        summary = summary_rows([record], 1)[0]
        self.assertEqual(summary["completed"], 0)
        self.assertEqual(summary["unverified"], 1)

    def test_unknown_task_is_not_counted(self):
        record = {
            "task_id": "T99",
            "model_requested": "test/mock:free",
            "trial": 1,
            "status": "completed",
            "raw_output": "{}",
        }
        row = evidence_rows([record], {c["id"]: c for c in load_cases()})[0]
        self.assertEqual(row["status"], "unverified")
        self.assertIsNone(row["pass"])
        summary = summary_rows([record], 1)[0]
        self.assertEqual(summary["unverified"], 1)
        self.assertEqual(summary["completed"], 0)


class MissingPromptEvidenceTests(unittest.TestCase):
    def test_missing_prompt_hash_is_unverified(self):
        case = load_cases({"T01"})[0]
        record = {
            "task_id": "T01",
            "model_requested": "test/mock:free",
            "trial": 1,
            "status": "completed",
            "raw_output": json.dumps(reference_answer(case)),
        }
        row = evidence_rows([record], {"T01": case})[0]
        self.assertEqual(row["status"], "unverified")
        self.assertIsNone(row["score"])
        self.assertEqual(summary_rows([record], 1)[0]["completed"], 0)


if __name__ == "__main__":
    unittest.main()
