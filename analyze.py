#!/usr/bin/env python3
"""Make a reproducible report from ACTUAL OpenRouter output JSONL. No inferred scores."""

from __future__ import annotations
import argparse
from collections import defaultdict
from pathlib import Path
import json
from run_eval import summarize, effective_status
from tasks import ROOT, load_cases


def report(records: list[dict], trials: int) -> str:
    s = summarize(records, trials)
    lines = [
        "# ChangeImpactBench experimental results",
        "",
        "This report only summarizes OpenRouter responses saved by the runner. API failures",
        "and truncated/empty generations are excluded from model accuracy; incomplete pass^k groups are not guessed.",
        "",
        f"Expected trials per task: **{trials}**",
        "",
        "| Requested model | Actual model ID(s) returned | Completed | API errors | Incomplete/empty | Exact pass | Mean partial score | pass^k (complete tasks only) |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for model, stats in s.items():
        actual = sorted(
            {
                r.get("model_returned", "unknown")
                for r in records
                if r["model_requested"] == model and effective_status(r) == "completed"
            }
        )

        def fmt(x):
            return "N/A" if x is None else f"{x:.1%}"

        lines.append(
            f"| `{model}` | {', '.join('`' + x + '`' for x in actual) or '—'} | {stats['completed']} | {stats['api_errors']} | {stats['incomplete_generations'] + stats['empty_generations']} | {fmt(stats['pass_rate_on_completed'])} | {fmt(stats['mean_partial_score'])} | {fmt(stats['pass_power_k'])} ({stats['full_trial_groups']} tasks) |"
        )
    lines += ["", "## Per-task results", ""]
    for case in load_cases():
        lines += [f"### {case['id']}: {case['title']}", ""]
        for model in s:
            g = [r for r in records if r["model_requested"] == model and r["task_id"] == case["id"]]
            completed = [r for r in g if effective_status(r) == "completed"]
            passes = sum(bool(r["grade"]["pass"]) for r in completed)
            lines.append(
                f"- `{model}`: {passes}/{len(completed)} exact passes; {sum(effective_status(r) == 'api_error' for r in g)} API errors; {sum(effective_status(r) in ('incomplete_generation', 'empty_generation') for r in g)} incomplete/empty generations."
            )
            failures = [r for r in completed if not r["grade"]["pass"]]
            if failures:
                f = failures[0]
                lines.append(
                    f"  - Example failure: trial {f['trial']}, affected-set F1={f['grade']['affected_f1']}; root correct={f['grade']['root_correct']}; fix correct={f['grade']['fix_correct']}. Inspect raw output in the JSONL (this is a scoring description, **not yet a human-reviewed causal explanation**)."
                )
        lines.append("")
    lines += [
        "## Review checklist",
        "",
        "- [ ] Check failed raw transcripts against the prompt and independently verified oracle.",
        "- [ ] Distinguish API/formatting errors from genuine reasoning failures.",
        "- [ ] Write an evidence-backed explanation for each task's failures (no generic claims).",
        "- [ ] Record service/provider/model revisions and pricing/usage for reproducibility.",
        "- [ ] Add your own expert review and whether AI helped draft tasks.",
        "- [ ] Record the exact date, runtime and provider environment.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="results/openrouter_runs.jsonl")
    p.add_argument("--trials", type=int, default=3)
    p.add_argument("--output", default="results/report.md")
    a = p.parse_args()
    infile = ROOT / a.input
    if not infile.is_file():
        raise SystemExit(f"No run found at {infile}. Run run_eval.py first.")
    records = [json.loads(line) for line in infile.read_text().splitlines() if line.strip()]
    out = report(records, a.trials)
    outfile = ROOT / a.output
    outfile.parent.mkdir(parents=True, exist_ok=True)
    outfile.write_text(out, encoding="utf-8")
    print(out)
    print(f"Wrote {outfile}")
