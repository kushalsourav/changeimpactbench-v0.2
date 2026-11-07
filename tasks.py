"""Immutable task loader and prompt compositor. Reference answers are never exposed."""

from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_cases(ids: set[str] | None = None) -> list[dict]:
    out = []
    for path in sorted((ROOT / "tasks").glob("*.json")):
        case = json.loads(path.read_text(encoding="utf-8"))
        if ids is None or case["id"] in ids:
            out.append(case)
    if ids is not None and ids != {x["id"] for x in out}:
        raise ValueError(f"unknown task(s): {ids - {x['id'] for x in out}}")
    return out


def make_prompt(case: dict) -> str:
    """Only public case data crosses the API boundary. No reference/answer keys."""
    public = {
        k: case[k]
        for k in ("id", "title", "context", "semantics", "facts", "hypotheses", "actions")
    }
    advanced_note = ""
    if case.get("benchmark_version") == "advanced-v0.4":
        advanced_note = (
            "ADVANCED CASE: A needs_at_least:{count:N,of:[...]} service becomes "
            "unavailable if fewer than N listed dependencies remain healthy. "
            "A repair with changes:[{path,value},...] applies all listed changes atomically. "
            "The causal hypothesis may describe TWO simultaneous local defects; "
            "choose the single hypothesis matching the combined observed mechanism. "
            "Treat recorded observations as evidence, not as additional health rules.\n\n"
        )
    if case.get("benchmark_version") == "advanced-v0.5":
        advanced_note = (
            "ADVANCED CAUSAL CASE: Direct local failures are defined ONLY by facts.local_rules. "
            "Each rule names its service and a when condition; that service fails locally if "
            "and only if its condition evaluates true. Conditions use all:[...], any:[...], "
            "not:{...}, or {left,op,right}, with op one of eq,ne,gt,ge,lt,le. "
            "Operands are {path:[...]} (lookup in facts), {literal:value}, or "
            "{sum:[operand,...]}, or {product:[operand,...]}. Comparisons are strict "
            "where gt/lt is used; equality is healthy "
            "for a > threshold rule. Observations and historical notes are context only and "
            "never override the explicit local rules. Apply multi-edit repairs atomically. "
            "For needs_at_least:{count:N,of:[...]}, a service needs at least N healthy listed "
            "dependencies. A valid complete repair must also preserve previously healthy services. "
            "Choose the hypothesis explaining the exact combination of locally failed services.\n\n"
        )
    advanced = case.get("benchmark_version") in ("advanced-v0.4", "advanced-v0.5")
    repair_instruction = (
        "To evaluate each action, apply ALL of its changes simultaneously to the AFTER facts"
        if advanced
        else "To evaluate each action, apply ONLY its single stated modification to the AFTER facts"
    )
    cause_instruction = (
        "the combined local failure mechanisms responsible for the outage"
        if advanced
        else "the concrete local check responsible for the outage"
    )
    return (
        "You are an SRE reviewing a fictional, fully-specified production incident. "
        "All data below are synthetic. Treat the stated behavior rules as authoritative, "
        "not real-world unstated defaults. Independently analyze the AFTER state.\n\n"
        "The dependency graph lists services by id. A service fails if it fails its own "
        "local check, OR any of needs_all is down, OR (if needs_any is nonempty) "
        "every item of needs_any is down. An empty needs_all or needs_any imposes no requirement. "
        "Failures propagate to a fixed point. Services not locally failing are initially healthy.\n\n"
        + repair_instruction
        + ", and recompute all service availability from scratch. A valid complete fix leaves "
        "NO failed services (including ones healthy before). Select the lowest-cost complete fix; "
        "costs are distinct among complete fixes.\n\n"
        + advanced_note
        + "Return EXACTLY one JSON object with three fields: "
        '{"failed_services":["service-id",...],"root_cause":"Hxx","fix_id":"Axx"}. '
        "failed_services must list ALL unavailable nodes (including directly failing components); "
        "order does not matter. root_cause must be the one hypothesis ID that describes "
        + cause_instruction
        + ". fix_id is the lowest-cost "
        "complete repair. No explanation, code fences, or other keys.\n\n"
        "INCIDENT DOSSIER (public information):\n"
        + json.dumps(public, ensure_ascii=False, indent=2, sort_keys=True)
    )
