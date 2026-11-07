"""Read-only agentic evidence, independently regraded from observable native tool calls.

No hidden chain of thought, simulated provider replies or historical single-turn data.
"""
from __future__ import annotations
from datetime import datetime
import json
from pathlib import Path
from typing import Any
from agent_graph import TASK_IDS as AGENT_TASKS, replay_record, GRAPH_BASE
from oracle import patch_facts, reference_answer, reference_audit, simulate
from tasks import ROOT

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


def audit_record(record: dict, cases: dict[str, dict] | None = None) -> dict:
    """Recompute evidence and score, never trusting saved grades or observations."""
    status = record.get('status', 'unknown')
    result = {'status':status, 'grade':None, 'stored_grade_matches':None,
              'prompt_sha_matches':None, 'reference_matches':None,
              'warnings':[], 'expected':None}
    task_id = record.get('task_id')
    if task_id not in AGENT_TASKS:
        result['warnings'].append('Not an active LangGraph benchmark version')
        result['status'] = 'unverified'
        return result
    replay = replay_record(record)
    expected = replay['expected']
    seed = GRAPH_BASE[task_id]
    reference_path = ROOT / 'reference' / f'{seed}.json'
    try:
        historical_reference = json.loads(reference_path.read_text(encoding='utf-8')) if reference_path.is_file() else None
        if task_id.endswith(('V5', 'V6N', 'V6CF')):
            # Verify the historic reference independently in original names,
            # then verify the encoded V5/V6 replay against the versioned oracle.
            # No bypass: BOTH comparisons must succeed, and the task's frozen
            # source/prompt/trajectory hashes are checked by replay_record.
            from oracle import reference_answer
            from benchmarks.spec import source_case, service_codes
            original = reference_answer(source_case(task_id))
            encoded = dict(original)
            codes = service_codes(task_id)
            encoded['failed_services'] = sorted(codes[n] for n in original['failed_services'])
            ref_ok = historical_reference == reference_answer(source_case(seed + 'V4')) and encoded == expected
        else:
            ref_ok = historical_reference == expected
    except (ValueError, OSError):
        ref_ok = False
    result.update({'expected': expected,
                   'prompt_sha_matches':replay['verified'],
                   'reference_matches':ref_ok, 'grade':replay['grade'],
                   'warnings':list(replay['warnings']),
                   'unsafe_committed':replay.get('unsafe_committed')})
    if not ref_ok:
        result['warnings'].append(f'Synthetic source reference {seed} mismatches current oracle')
    if replay['grade'] is not None:
        saved = record.get('grade')
        result['stored_grade_matches'] = isinstance(saved, dict) and all(
            saved.get(key) == replay['grade'].get(key) for key in
            ('pass','strict_pass','score','affected_f1','root_correct','fix_correct',
             'recovery_safe','recovery_success','unsafe_commit','violations',
             'procedure_score','protocol_errors','counterfactual_checks','commit_was_simulated')
        )
        if not result['stored_grade_matches']:
            result['warnings'].append('Stored score differs from independent replay')
    if not replay['verified'] or not ref_ok:
        result['status'] = 'unverified'
    return result

def evidence_rows(records: list[dict], cases: dict[str, dict]) -> list[dict]:
    rows = []
    for r in records:
        a = audit_record(r, cases)
        # Invalid prompt/references and unknown task IDs must not look like
        # verified model successes in either the evidence table or its charts.
        verified = (
            (r.get('task_id') in AGENT_TASKS)
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
                "condition": "agentic",
                "unsafe_commit": a.get('unsafe_committed') if r.get('task_id') in AGENT_TASKS else None,
                "recovery_success": (a['grade'] or {}).get('recovery_success')
                    if r.get('task_id') in AGENT_TASKS else None,
                "tool_calls": len(r.get('trajectory', [])) if r.get('task_id') in AGENT_TASKS else None,
            }
        )
    return rows


def summary_rows(records: list[dict], k: int) -> list[dict]:
    """Group only independently verified completed model replies. Report errors separately."""
    grouped: dict[str, list[tuple[dict, dict]]] = {}
    for record in records:
        grouped.setdefault(record.get('model_requested','unknown'), []).append((record,audit_record(record)))
    rows=[]
    for model, items in grouped.items():
        completed=[(r,a) for r,a in items if a['status']=='completed' and a.get('grade')]
        api_errors=sum(a['status']=='api_error' for _,a in items)
        incomplete=sum(a['status'] in ('incomplete_generation','empty_generation') for _,a in items)
        unverified=sum(a['status']=='unverified' for _,a in items)
        passed=sum(a['grade']['strict_pass'] is True for _,a in completed)
        score=sum(a['grade']['score'] for _,a in completed) / len(completed) if completed else None
        complete_by_task: dict[str,list[dict]]={}
        for record,audit in completed:
            complete_by_task.setdefault(record['task_id'],[]).append({'trial':record.get('trial'), 'pass':audit['grade']['strict_pass']})
        full=[v for v in complete_by_task.values() if len({e['trial'] for e in v})==k]
        rows.append({'model':model,'completed':len(completed),'passed':passed,
            'wrong':len(completed)-passed,'api_errors':api_errors,'incomplete':incomplete,
            'unverified':unverified,'exact_pass_rate':round(passed/len(completed),4) if completed else None,
            'mean_partial':round(score,4) if score is not None else None,
            'pass_power_k':round(sum(all(e['pass'] for e in group) for group in full)/len(full),4) if full and k>=2 else None,
            'full_trial_groups':len(full),
            'agentic_non_gradeable':sum(a['status'] in ('budget_exhausted','unsupported_tool_protocol','incomplete_workflow') for _,a in items),
            'unsafe_committed_episodes':sum(a.get('unsafe_committed') is True for _,a in items)})
    return rows

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
