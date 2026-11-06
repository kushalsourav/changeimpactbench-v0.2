"""Exact, auditable scoring; no LLM-as-judge and no substring tricks."""

from __future__ import annotations

import json
import math
from typing import Any


class InvalidAnswer(ValueError):
    pass


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise InvalidAnswer(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_answer(raw: str) -> dict:
    """Parse one JSON object. Optional surrounding markdown fence is harmless."""
    if not isinstance(raw, str):
        raise InvalidAnswer("answer is not text")
    raw = raw.strip()
    if raw.startswith("```json") and raw.endswith("```"):
        raw = raw[7:-3].strip()
    elif raw.startswith("```") and raw.endswith("```"):
        raw = raw[3:-3].strip()
    try:
        payload = json.loads(raw, object_pairs_hook=_no_duplicate_keys)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise InvalidAnswer(f"malformed JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise InvalidAnswer("expected a single JSON object")
    required = {"failed_services", "root_cause", "fix_id"}
    if set(payload) != required:
        raise InvalidAnswer(f"expected exactly keys {sorted(required)}")
    services = payload["failed_services"]
    if not isinstance(services, list) or any(not isinstance(x, str) for x in services):
        raise InvalidAnswer("failed_services must be an array of strings")
    if len(services) != len(set(services)):
        raise InvalidAnswer("duplicate failed service")
    if any(not x or x != x.strip() for x in services):
        raise InvalidAnswer("invalid service identifier")
    for fld in ("root_cause", "fix_id"):
        if (
            not isinstance(payload[fld], str)
            or not payload[fld]
            or payload[fld] != payload[fld].strip()
        ):
            raise InvalidAnswer(f"{fld} must be a nonblank exact ID")
    return payload


def grade(raw: str, expected: dict) -> dict:
    """Affected-set F1 worth 0.5; causal ID 0.25; safe remediation 0.25.

    Any format error receives 0 (not counted as a network/API failure).
    An exact pass requires matching all 3 fields, regardless of score rounding.
    """
    try:
        ans = parse_answer(raw)
    except InvalidAnswer as exc:
        return {
            "score": 0.0,
            "pass": False,
            "format_valid": False,
            "error": str(exc),
            "affected_f1": 0.0,
            "root_correct": False,
            "fix_correct": False,
        }
    truth, predicted = set(expected["failed_services"]), set(ans["failed_services"])
    tp = len(truth & predicted)
    precision = tp / len(predicted) if predicted else (1.0 if not truth else 0.0)
    recall = tp / len(truth) if truth else (1.0 if not predicted else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    root_ok = ans["root_cause"] == expected["root_cause"]
    fix_ok = ans["fix_id"] == expected["fix_id"]
    exact = predicted == truth and root_ok and fix_ok
    return {
        "score": round(0.5 * f1 + 0.25 * int(root_ok) + 0.25 * int(fix_ok), 5),
        "pass": bool(exact),
        "format_valid": True,
        "error": None,
        "affected_f1": round(f1, 5),
        "root_correct": root_ok,
        "fix_correct": fix_ok,
    }
