"""Read-only dashboard helpers. No networking, no API-key access, no fabricated data.

All model outcomes are reconstructed from raw JSONL and checked with the same
oracle/grader used by the runner. No provider's hidden chain of thought is shown.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from hashlib import sha256
import io
import json
from pathlib import Path
from typing import Any

from grader import grade, parse_answer, InvalidAnswer
from agentic import TASK_ID as AGENT_TASK, replay_record as replay_agent, source_case as agent_source_case
from agentic_v2 import TASK_ID as AGENT_TASK_V2, replay_record as replay_agent_v2
from agentic_v3 import TASK_ID as AGENT_TASK_V3, replay_record as replay_agent_v3
from agentic_suite import TASK_IDS as SUITE_TASKS, SPECS as SUITE_SPECS, replay_record as replay_suite
AGENT_TASKS = {AGENT_TASK, AGENT_TASK_V2, AGENT_TASK_V3} | SUITE_TASKS
from oracle import patch_facts, reference_answer, reference_audit, simulate
from run_eval import effective_status, summarize
from tasks import ROOT, make_prompt, load_cases


def available_runs(root: Path = ROOT) -> list[Path]:
    folder = root / "results"
    return sorted(
        (p for p in folder.glob("*.jsonl") if p.is_file() and not p.name.startswith("_")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def parse_jsonl(data: str) -> list[dict]:
    results = []
    for number, line in enumerate(data.splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON at JSONL line {number}: {exc.msg}") from exc
        if not isinstance(rec, dict):
            raise ValueError(f"JSONL line {number} must be an object")
        for key in ("task_id", "model_requested", "trial"):
            if key not in rec:
                raise ValueError(f"JSONL line {number} is missing '{key}'")
        results.append(rec)
    return results


def expected_trials_from_records(records: list[dict]) -> int:
    return max((int(x.get("trial", 1)) for x in records), default=3)


def audit_record(record: dict, cases: dict[str, dict]) -> dict:
    """Compute an independent, visible trace of what can actually be verified."""
    status = effective_status(record)
    out = {
        "status": status,
        "grade": None,
        "stored_grade_matches": None,
        "prompt_sha_matches": None,
        "reference_matches": None,
        "warnings": [],
        "expected": None,
    }
    task_id = record.get("task_id")
    if task_id in AGENT_TASKS:
        replay = ({AGENT_TASK: replay_agent, AGENT_TASK_V2: replay_agent_v2, AGENT_TASK_V3: replay_agent_v3, **{k:replay_suite for k in SUITE_TASKS}}[task_id])(record)
        expected = replay['expected']
        ref_seed = SUITE_SPECS[task_id]['seed'] if task_id in SUITE_TASKS else 'T08'
        ref_path = ROOT / 'reference' / f'{ref_seed}.json'
        try:
            reference_matches = (ref_path.is_file() and
                                 json.loads(ref_path.read_text(encoding='utf-8')) == expected)
        except (ValueError, OSError):
            reference_matches = False
        out.update({'expected': expected, 'prompt_sha_matches': replay['verified'],
                    'reference_matches': reference_matches,
                    'grade': replay['grade'], 'warnings': list(replay['warnings']),
                    'unsafe_committed': replay.get('unsafe_committed')})
        if not reference_matches:
            out['warnings'].append(f'Agentic source {ref_seed} reference has drifted')
        if replay['grade'] is not None:
            stored = record.get('grade')
            out['stored_grade_matches'] = (isinstance(stored, dict) and
                all(stored.get(k) == replay['grade'].get(k) for k in
                    ('pass', 'score', 'affected_f1', 'root_correct', 'fix_correct',
                     'recovery_safe', 'recovery_success', 'unsafe_commit', 'violations')))
            if task_id in ({AGENT_TASK_V2, AGENT_TASK_V3} | SUITE_TASKS) and out['stored_grade_matches']:
                out['stored_grade_matches'] = all(stored.get(k) == replay['grade'].get(k) for k in
                    ('procedure_score', 'protocol_errors', 'counterfactual_checks',
                     'commit_was_simulated', 'strict_pass'))
            if not out['stored_grade_matches']:
                out['warnings'].append('Stored agentic score does not match independent replay')
        if not replay['verified'] or not reference_matches:
            out['status'] = 'unverified'
        return out
    if task_id not in cases:
        out["warnings"].append(f"Unknown task {task_id}; cannot verify outcome")
        return out
    case = cases[task_id]
    reference = reference_answer(case)
    out["expected"] = reference
    stored_reference = ROOT / "reference" / (task_id + ".json")
    if stored_reference.exists():
        try:
            out["reference_matches"] = (
                json.loads(stored_reference.read_text(encoding="utf-8")) == reference
            )
        except (ValueError, OSError):
            out["reference_matches"] = False
        if out["reference_matches"] is False:
            out["warnings"].append("Stored reference differs from deterministic simulator")
    else:
        out["warnings"].append("Stored reference file is missing")
    expected_prompt = make_prompt(case)
    correct_hash = sha256(expected_prompt.encode("utf-8")).hexdigest()
    if record.get("prompt_sha256"):
        out["prompt_sha_matches"] = record["prompt_sha256"] == correct_hash
        if not out["prompt_sha_matches"]:
            out["warnings"].append(
                "Recorded prompt does not match current task; do NOT compare across versions"
            )
    elif "prompt" in record:
        out["prompt_sha_matches"] = record["prompt"] == expected_prompt
        if not out["prompt_sha_matches"]:
            out["warnings"].append("Recorded prompt differs from current task")
    else:
        out["warnings"].append(
            "No prompt or prompt hash recorded; original prompt cannot be verified"
        )
    if status == "completed":
        out["grade"] = grade(record.get("raw_output", ""), reference)
        stored = record.get("grade")
        if stored is not None:
            out["stored_grade_matches"] = all(
                stored.get(k) == out["grade"].get(k)
                for k in (
                    "score",
                    "pass",
                    "format_valid",
                    "affected_f1",
                    "root_correct",
                    "fix_correct",
                )
            )
            if not out["stored_grade_matches"]:
                out["warnings"].append(
                    "Stored grade differs from fresh grading; investigate before reporting"
                )
        else:
            out["warnings"].append("Completed model response has no saved grade")
    return out


def evidence_rows(records: list[dict], cases: dict[str, dict]) -> list[dict]:
    rows = []
    for r in records:
        a = audit_record(r, cases)
        # Invalid prompt/references and unknown task IDs must not look like
        # verified model successes in either the evidence table or its charts.
        verified = (
            (r.get('task_id') in cases or r.get('task_id') in AGENT_TASKS)
            and a['prompt_sha_matches'] is True
            and a['reference_matches'] is True
        )
        status = a['status'] if verified else 'unverified'
        g = (a['grade'] or {}) if status == 'completed' else {}
        usage = r.get("usage") or {}
        rows.append(
            {
                "model": r.get("model_requested", "?"),
                "actual_model": r.get("model_returned") or "—",
                "task": r.get("task_id", "?"),
                "trial": r.get("trial", "?"),
                "timestamp_utc": r.get("timestamp_utc", ""),
                "status": status,
                "pass": g.get("pass") if status == "completed" else None,
                "score": g.get("score") if status == "completed" else None,
                "affected_f1": g.get("affected_f1"),
                "root_correct": g.get("root_correct"),
                "fix_correct": g.get("fix_correct"),
                "format_valid": g.get("format_valid"),
                "latency_s": r.get("elapsed_seconds"),
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "reasoning_tokens": r.get("reasoning_tokens"),
                "finish_reason": r.get("finish_reason", ""),
                "prompt_verified": a["prompt_sha_matches"],
                "grade_verified": a["stored_grade_matches"],
                "reference_verified": a["reference_matches"],
                "warnings": " | ".join(a["warnings"]),
                "condition": "agentic" if r.get('task_id') in AGENT_TASKS else "single-turn",
                "unsafe_commit": a.get('unsafe_committed') if r.get('task_id') in AGENT_TASKS else None,
                "recovery_success": (a['grade'] or {}).get('recovery_success')
                    if r.get('task_id') in AGENT_TASKS else None,
                "tool_calls": len(r.get('trajectory', [])) if r.get('task_id') in AGENT_TASKS else None,
            }
        )
    return rows


def summary_rows(records: list[dict], k: int) -> list[dict]:
    """Regrade completed answers before summarizing; never turn HTTP errors into failures."""
    cases = {c["id"]: c for c in load_cases()}
    clean = []
    for r in records:
        updated = dict(r)
        a = audit_record(r, cases)
        # Keep suspicious prompt versions out of claimed results.
        if ((r.get('task_id') not in cases and r.get('task_id') not in AGENT_TASKS)
                or a["prompt_sha_matches"] is not True
                or a["reference_matches"] is not True):
            updated["status"] = "unverified"
        elif a["status"] == "completed" and a["grade"] is not None:
            updated["grade"] = a["grade"]
        else:
            updated["status"] = a["status"]
        clean.append(updated)
    grouped = summarize(clean, k)
    rows = []
    for model, s in grouped.items():
        rows.append(
            {
                "model": model,
                "completed": s["completed"],
                "passed": s["pass_count"],
                "wrong": s["completed"] - s["pass_count"],
                "api_errors": s["api_errors"],
                "incomplete": s["incomplete_generations"] + s["empty_generations"],
                "unverified": sum(
                    1
                    for r in clean
                    if r["model_requested"] == model and r["status"] == "unverified"
                ),
                "exact_pass_rate": s["pass_rate_on_completed"],
                "mean_partial": s["mean_partial_score"],
                "pass_power_k": s["pass_power_k"],
                "full_trial_groups": s["full_trial_groups"],
                "agentic_non_gradeable": sum(
                    1 for r in clean if r.get('model_requested') == model
                    and r.get('task_id') in AGENT_TASKS
                    and r.get('status') in ('unsupported_tool_protocol', 'budget_exhausted')
                ),
                "unsafe_committed_episodes": sum(
                    1 for r in clean if r.get('model_requested') == model
                    and r.get('task_id') in AGENT_TASKS
                    and audit_record(r, cases).get('unsafe_committed') is True
                ),
            }
        )
    return rows


def case_diagnostics(record: dict, case: dict) -> dict:
    expected = reference_answer(case)
    a = audit_record(record, {case["id"]: case})
    result = {
        "expected": expected,
        "grade": a["grade"],
        "can_parse": False,
        "predicted": None,
        "missed_services": [],
        "extra_services": [],
        "root_explanation": "",
        "repair_explanation": "",
    }
    if a["status"] != "completed":
        return result
    try:
        predicted = parse_answer(record.get("raw_output", ""))
        result["predicted"] = predicted
        result["can_parse"] = True
        result["missed_services"] = sorted(
            set(expected["failed_services"]) - set(predicted["failed_services"])
        )
        result["extra_services"] = sorted(
            set(predicted["failed_services"]) - set(expected["failed_services"])
        )
        root_lookup = {h["id"]: h["description"] for h in case["hypotheses"]}
        action_lookup = {x["id"]: x["meaning"] for x in case["actions"]}
        result["root_explanation"] = root_lookup.get(
            predicted["root_cause"], "Unrecognized hypothesis ID"
        )
        result["repair_explanation"] = action_lookup.get(
            predicted["fix_id"], "Unrecognized action ID"
        )
    except InvalidAnswer:
        pass
    return result


def topology_dot(case: dict, down: set[str], highlight: set[str] | None = None) -> str:
    """Graphviz DOT for the real topology. Edges point from dependency to consumer."""
    highlight = highlight or set()
    lines = [
        "digraph services {",
        "rankdir=LR;",
        'graph [bgcolor="transparent", pad="0.2"];',
        'node [shape=box, style="rounded,filled", fontname="Arial", fontsize=11, penwidth=1.3];',
        'edge [fontname="Arial", fontsize=9, color="#8994a6"];',
    ]
    for node in case["facts"]["topology"]:
        name = node["id"]
        is_down = name in down
        fill = "#fee2e2" if is_down else "#dcfce7"
        stroke = "#be123c" if is_down else "#16a34a"
        if name in highlight:
            stroke = "#7c3aed"
        lines.append(
            f'{json.dumps(name)} [fillcolor="{fill}",color="{stroke}",fontcolor="#1f2937",penwidth={"3" if name in highlight else "1.3"}];'
        )
        for dep in node.get("needs_all", []):
            lines.append(f'{json.dumps(dep)} -> {json.dumps(name)} [label="ALL"];')
        for dep in node.get("needs_any", []):
            lines.append(
                f'{json.dumps(dep)} -> {json.dumps(name)} [label="ANY",style="dashed",color="#64748b"];'
            )
        quorum = node.get("needs_at_least")
        if quorum:
            for dep in quorum["of"]:
                lines.append(
                    f"{json.dumps(dep)} -> {json.dumps(name)} "
                    f'[label="{quorum["count"]}/{len(quorum["of"])}",style="dotted"];'
                )
    lines.append("}")
    return "\n".join(lines)


def repair_state(case: dict, action_id: str) -> set[str]:
    action = next(a for a in case["actions"] if a["id"] == action_id)
    revised = patch_facts(case["facts"], action)
    failed, _ = simulate(case, revised)
    return failed
