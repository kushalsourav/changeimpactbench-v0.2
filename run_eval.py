#!/usr/bin/env python3
"""OpenRouter free-tier evaluator. No requests are made without a user API key."""

from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
from typing import Any

from grader import grade
from oracle import reference_answer, reference_audit
from tasks import ROOT, load_cases, make_prompt

API = "https://openrouter.ai/api/v1"
FREE_DEFAULTS = [
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
]


def get_json(url: str, token: str | None = None, post: dict | None = None) -> dict:
    data = json.dumps(post).encode("utf-8") if post is not None else None
    headers = {"Content-Type": "application/json", "User-Agent": "ChangeImpactBench/0.1"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(
        url, data=data, headers=headers, method="POST" if data is not None else "GET"
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Don't write raw error bodies; providers may reflect request details.
        detail = exc.read(600).decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {exc.code} from OpenRouter: {detail}") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"OpenRouter request failed: {exc}") from None


def fetch_free_models() -> list[dict]:
    raw = get_json(API + "/models")
    free = []
    for d in raw.get("data", []):
        model_id = d.get("id", "")
        pricing = d.get("pricing") or {}
        # Deliberately restrict to free variants, not zero-priced paid-route aliases.
        try:
            free_prices = (
                Decimal(str(pricing.get("prompt", "?"))) == 0
                and Decimal(str(pricing.get("completion", "?"))) == 0
            )
        except (InvalidOperation, TypeError):
            free_prices = False
        if model_id.endswith(":free") and free_prices:
            free.append(
                {
                    "id": model_id,
                    "name": d.get("name", ""),
                    "context_length": d.get("context_length"),
                }
            )
    return sorted(free, key=lambda d: d["id"])


def extract_content(data: dict) -> tuple[str, str, Any]:
    choice = data.get("choices", [{}])[0]
    message = choice.get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        out = content
    elif isinstance(content, list):
        out = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
    else:
        out = ""
    return out, data.get("model", ""), data.get("usage") or {}


def effective_status(record: dict) -> str:
    """Normalize older saved runs too, without changing immutable raw JSONL data."""
    status = record.get("status", "unknown")
    if status == "completed":
        # A 200 response can contain no answer if the entire completion budget was
        # consumed by reasoning. The provider reported 'length', not a model answer.
        if record.get("finish_reason") == "length":
            return "incomplete_generation"
        if not (record.get("raw_output") or "").strip() and "raw_output" in record:
            return "empty_generation"
    return status


def reasoning_tokens(usage: dict) -> int | None:
    details = usage.get("completion_tokens_details") or {}
    n = details.get("reasoning_tokens")
    if n is None:
        return None
    try:
        return int(n)
    except (ValueError, TypeError):
        return None


def make_record(
    model: str, case: dict, trial: int, temperature: float, max_tokens: int, prompt: str
) -> dict:
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "task_id": case["id"],
        "benchmark_version": case.get("benchmark_version", "baseline-v0.1"),
        "model_requested": model,
        "trial": trial,
        "temperature_requested": temperature,
        "max_tokens_requested": max_tokens,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt": prompt,
    }


def summarize(records: list[dict], expected_trials: int) -> dict:
    groups: dict[str, list[dict]] = {}
    for r in records:
        groups.setdefault(r["model_requested"], []).append(r)
    summary = {}
    for model, group in groups.items():
        completed = [r for r in group if effective_status(r) == "completed"]
        api_errors = [r for r in group if effective_status(r) == "api_error"]
        incomplete = [r for r in group if effective_status(r) == "incomplete_generation"]
        empty = [r for r in group if effective_status(r) == "empty_generation"]
        passes = sum(bool(r["grade"]["pass"]) for r in completed)
        tasks: dict[str, list[dict]] = {}
        for r in completed:
            tasks.setdefault(r["task_id"], []).append(r)
        fully_tested = [
            g for g in tasks.values() if len({r["trial"] for r in g}) == expected_trials
        ]
        consistently_passing = [g for g in fully_tested if all(r["grade"]["pass"] for r in g)]
        summary[model] = {
            "attempted": len(group),
            "completed": len(completed),
            "api_errors": len(api_errors),
            "incomplete_generations": len(incomplete),
            "empty_generations": len(empty),
            "pass_count": passes,
            "pass_rate_on_completed": round(passes / len(completed), 4) if completed else None,
            "mean_partial_score": round(
                sum(r["grade"]["score"] for r in completed) / len(completed), 4
            )
            if completed
            else None,
            "full_trial_groups": len(fully_tested),
            "pass_power_k": round(len(consistently_passing) / len(fully_tested), 4)
            if fully_tested and expected_trials >= 2
            else None,
            "k": expected_trials,
            "note": "pass^k uses only full groups of complete responses; HTTP errors, empty responses and token-limited generations are separately reported, not scored as reasoning failures",
        }
    return summary


def load_previous(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def run(args: argparse.Namespace) -> None:
    cases = load_cases(set(args.tasks) if args.tasks else None)
    if not args.tasks and not any((args.list_free, args.self_check, args.preview)):
        # Preserve the existing default experiment; new research cases require
        # explicit --tasks so that benchmark versions cannot be silently pooled.
        cases = [
            case
            for case in cases
            if case.get("benchmark_version", "baseline-v0.1") == "baseline-v0.1"
        ]
    if args.list_free:
        for entry in fetch_free_models():
            print(f"{entry['id']:<60} {entry['name']}")
        return
    if args.self_check:
        for case in cases:
            expected = reference_answer(case)
            with (ROOT / "reference" / (case["id"] + ".json")).open() as fh:
                stored = json.load(fh)
            assert expected == stored, f"Drift in {case['id']} oracle"
            verified = grade(json.dumps(expected), expected)
            assert verified["pass"], f"Oracle did not pass {case['id']}"
            print(
                f"{case['id']} OK | {len(expected['failed_services'])} down | root={expected['root_cause']} | lowest-cost fix={expected['fix_id']}"
            )
        print(
            "All reference solutions pass their grader. Run python -m unittest discover -s tests for negative tests."
        )
        return
    if args.preview:
        for case in cases:
            prompt = make_prompt(case)
            print(
                f"{case['id']} {case['title']}: {len(prompt)} chars, {len(prompt.split())} approx words"
            )
        return
    versions = {case.get("benchmark_version", "baseline-v0.1") for case in cases}
    if len(versions) > 1:
        raise SystemExit(
            "Do not mix baseline and advanced tasks in one run; select a single benchmark version"
        )
    if not args.models:
        raise SystemExit("Supply --models or omit to use the default free models")
    if any(not m.endswith(":free") for m in args.models):
        raise SystemExit("Only :free model IDs are accepted to prevent accidental charges")
    token = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not token:
        raise SystemExit("OPENROUTER_API_KEY missing; no API calls made. See README.")
    needed = len(cases) * len(args.models) * args.trials
    if needed > args.max_requests:
        raise SystemExit(
            f"Planned {needed} requests exceeds --max-requests={args.max_requests}. Reduce trials/models/tasks."
        )
    if args.trials < 1 or args.trials > 10:
        raise SystemExit("--trials must be 1..10")
    if args.delay < 3:
        raise SystemExit("--delay must be >=3 seconds to respect free-tier per-minute limits")
    if not args.skip_catalog_check:
        catalog = {x["id"] for x in fetch_free_models()}
        invalid = [m for m in args.models if m not in catalog]
        if invalid:
            raise SystemExit(
                f"Unavailable/non-free IDs: {invalid}. Run --list-free to see options."
            )
    outfile = ROOT / args.output
    outfile.parent.mkdir(parents=True, exist_ok=True)
    previous = load_previous(outfile)
    old_map = {(r["model_requested"], r["task_id"], r["trial"]): r for r in previous}
    if previous and not args.resume:
        raise SystemExit("Output file already exists. Use --resume or choose a new --output.")
    if previous:
        for r in previous:
            if r["model_requested"] not in args.models or r["task_id"] not in {
                c["id"] for c in cases
            }:
                raise SystemExit(
                    "Resume output contains a model/task outside this run; use a different --output"
                )
            case = next(c for c in cases if c["id"] == r["task_id"])
            if r["prompt_sha256"] != hashlib.sha256(make_prompt(case).encode()).hexdigest():
                raise SystemExit(
                    "Task changed since saved run; use new --output to avoid misleading results"
                )
            if (
                r["temperature_requested"] != args.temperature
                or r["max_tokens_requested"] != args.max_tokens
                or r.get("reasoning_effort_requested") != getattr(args, "reasoning_effort", None)
            ):
                raise SystemExit("Run settings changed; use a different --output")
    pending = [
        (m, c, t)
        for m in args.models
        for c in cases
        for t in range(1, args.trials + 1)
        if (m, c["id"], t) not in old_map
    ]
    print(
        f"OpenRouter free-only run: {len(pending)} requests pending; {len(previous)} prior. No paid models allowed."
    )
    records = list(previous)
    for idx, (model, case, trial) in enumerate(pending, 1):
        prompt = make_prompt(case)
        r = make_record(model, case, trial, args.temperature, args.max_tokens, prompt)
        r["reasoning_effort_requested"] = getattr(args, "reasoning_effort", None)
        now = time.perf_counter()
        print(f"[{idx}/{len(pending)}] {model} {case['id']} trial={trial} ...", flush=True)
        try:
            payload = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a precise reliability engineer. Respond with only the JSON object requested by the user.",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": args.temperature,
                "max_tokens": args.max_tokens,
                "stream": False,
            }
            # Optional: provider support varies; keep the requested setting on record.
            if getattr(args, "reasoning_effort", None):
                payload["reasoning"] = {"effort": args.reasoning_effort}
            data = get_json(API + "/chat/completions", token, payload)
            raw, model_actual, usage = extract_content(data)
            finish = data.get("choices", [{}])[0].get("finish_reason")
            status = (
                "incomplete_generation"
                if finish == "length"
                else "empty_generation"
                if not raw.strip()
                else "completed"
            )
            r.update(
                {
                    "status": status,
                    "model_returned": model_actual,
                    "response_id": data.get("id"),
                    "finish_reason": finish,
                    "usage": usage,
                    "reasoning_tokens": reasoning_tokens(usage),
                    "raw_output": raw,
                    "elapsed_seconds": round(time.perf_counter() - now, 3),
                }
            )
            if status == "completed":
                r["grade"] = grade(raw, reference_answer(case))
                print(f"    score={r['grade']['score']}, pass={r['grade']['pass']}", flush=True)
            else:
                print(
                    f"    {status}: finish_reason={finish}, visible_characters={len(raw)}, "
                    f"reasoning_tokens={r['reasoning_tokens']} (not graded)",
                    flush=True,
                )
        except Exception as exc:
            # Not a model response; do not score transport failures as reasoning failures.
            r.update(
                {
                    "status": "api_error",
                    "error": str(exc),
                    "elapsed_seconds": round(time.perf_counter() - now, 3),
                }
            )
            print(f"    API error: {exc}", file=sys.stderr, flush=True)
        # Write every trial immediately to avoid losing progress.
        with outfile.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        records.append(r)
        if idx < len(pending):
            time.sleep(args.delay)
    summary = summarize(records, args.trials)
    summary_path = outfile.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"Run saved: {outfile}")
    print(f"Summary saved: {summary_path}")
    print(json.dumps(summary, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument(
        "--list-free",
        action="store_true",
        help="Fetch live OpenRouter :free catalog (no API key needed)",
    )
    mode.add_argument(
        "--self-check",
        action="store_true",
        help="Verify all reference solutions locally, no API usage",
    )
    mode.add_argument("--preview", action="store_true", help="Show prompt sizes, no API usage")
    ap.add_argument("--models", nargs="+", default=FREE_DEFAULTS)
    ap.add_argument("--tasks", nargs="+", default=[], help="e.g. T01 T02")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--max-requests", type=int, default=45)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=2500)
    ap.add_argument(
        "--reasoning-effort",
        choices=["none", "minimal", "low", "medium", "high"],
        default=None,
        help="Optional OpenRouter reasoning effort. Provider support varies; record separately.",
    )
    ap.add_argument(
        "--delay", type=float, default=4.0, help="seconds between requests, for rate limiting"
    )
    ap.add_argument("--output", default="results/openrouter_runs.jsonl")
    ap.add_argument(
        "--resume", action="store_true", help="Skip already recorded trials (even prior API errors)"
    )
    ap.add_argument(
        "--skip-catalog-check",
        action="store_true",
        help="Only if catalog GET fails; still enforces :free suffix",
    )
    args = ap.parse_args()
    run(args)


if __name__ == "__main__":
    main()
