"""Deterministic reference simulator for ChangeImpactBench.

This code is NEVER sent to models. It models five independent families of
production incidents using explicit task facts and graph reachability.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

CAUSE_IDS = {
    "RW01": "H03", "RW02": "H02", "RW03": "H02",
    "RW04": "H02", "RW05": "H03", "RW06": "H01",
    "T01": "H03",
    "T02": "H01",
    "T03": "H04",
    "T04": "H02",
    "T05": "H03",
    "T06": "H04",
    "T07": "H02",
    "T08": "H04",
    "T09": "H02",
    "T10": "H05",
    "T11": "H03",
    "T12": "H01",
}


def patch_facts(facts: dict, action: dict) -> dict:
    """Apply an atomic repair (one or more edits) to a fresh facts snapshot.

    Legacy actions contain path/value; advanced actions may supply ``changes``.
    Reference answers are never sent to the model.
    """
    out = deepcopy(facts)
    # V6 conditional operations are unavailable if their documented readiness
    # requirement is false. Return an unchanged copy so a simulation reveals
    # a no-op, without treating a model's plan as a real state mutation.
    requirement = action.get('precondition')
    if requirement is not None:
        value = facts
        for key in requirement['path']:
            value = value[key]
        if value != requirement['equals']:
            return out
    edits = action.get("changes", [action])
    if not edits:
        raise ValueError("A repair must contain at least one change")
    visited = set()
    for edit in edits:
        parts = edit["path"]
        key = tuple(parts)
        if not parts or key in visited:
            raise ValueError("Empty or duplicate repair path")
        visited.add(key)
        cur = out
        for part in parts[:-1]:
            cur = cur[part]
        if parts[-1] not in cur:
            raise ValueError("Action path does not exist: " + ".".join(parts))
        cur[parts[-1]] = edit["value"]
    return out



def _operand(expr: dict, facts: dict) -> Any:
    """Resolve an explicit operand; never execute model-authored code."""
    if not isinstance(expr, dict) or len(expr) != 1:
        raise ValueError("Invalid rule operand")
    if "literal" in expr:
        return expr["literal"]
    if "path" in expr:
        value: Any = facts
        path = expr["path"]
        if not isinstance(path, list) or not path or any(not isinstance(k, str) for k in path):
            raise ValueError("Invalid local-rule path")
        for key in path:
            value = value[key]
        return value
    if "sum" in expr or "product" in expr:
        operation = next(iter(expr))
        members = expr[operation]
        if not isinstance(members, list) or not members:
            raise ValueError("Invalid numeric expression")
        values = [_operand(item, facts) for item in members]
        if any(type(v) not in (int, float) for v in values):
            raise ValueError("Numeric expression requires numeric operands")
        if operation == "sum":
            return sum(values)
        result = 1
        for value in values:
            result *= value
        return result
    raise ValueError("Unknown local-rule operand")


def _condition(expr: dict, facts: dict) -> bool:
    """Pure declarative boolean evaluator, shared by all advanced-v0.5 tasks."""
    if not isinstance(expr, dict):
        raise ValueError("Invalid local-rule condition")
    if set(expr) in ({"all"}, {"any"}):
        label = next(iter(expr))
        items = expr[label]
        if not isinstance(items, list) or not items:
            raise ValueError("Condition group cannot be empty")
        matches = [_condition(item, facts) for item in items]
        return all(matches) if label == "all" else any(matches)
    if set(expr) == {"not"}:
        return not _condition(expr["not"], facts)
    if set(expr) != {"left", "op", "right"}:
        raise ValueError("Unknown local-rule predicate")
    left, right = _operand(expr["left"], facts), _operand(expr["right"], facts)
    op = expr["op"]
    if op == "eq":
        return left == right
    if op == "ne":
        return left != right
    if type(left) not in (int, float) or type(right) not in (int, float):
        raise ValueError("Ordering comparisons require numeric operands")
    if op == "gt":
        return left > right
    if op == "ge":
        return left >= right
    if op == "lt":
        return left < right
    if op == "le":
        return left <= right
    raise ValueError(f"Unknown comparison operator: {op}")


def _rule_failures(facts: dict) -> set[str]:
    topology_ids = {node["id"] for node in facts["topology"]}
    seen: set[str] = set()
    failed: set[str] = set()
    for entry in facts["local_rules"]:
        name = entry["service"]
        if name in seen or name not in topology_ids:
            raise ValueError(f"Repeated or missing local-rule node {name}")
        seen.add(name)
        if _condition(entry["when"], facts):
            failed.add(name)
    return failed

def initial_failures(case_id: str, facts: dict) -> tuple[set[str], str | None]:
    """Compute directly broken components and the governing causal hypothesis.

    Other components can fail only via dependencies. We do not infer failure
    from model answers or logs: outcomes derive entirely from supplied facts.
    """
    if "local_rules" in facts:
        failed = _rule_failures(facts)
        return failed, CAUSE_IDS[case_id] if failed else None
    if case_id == "T01":
        failed = {
            "policy-" + region
            for region, d in facts["regions"].items()
            if d["rollout_enabled"]
            and d["parser_version"] < 28
            and (d["tenant_id"] is None or d["tenant_id"].strip() == "")
        }
        return failed, CAUSE_IDS["T01"] if failed else None
    if case_id == "T02":
        failed = {
            "route-" + zone
            for zone, d in facts["zones"].items()
            if not d["export_enabled"]
            or (d["policy_version"] >= 2 and d["community"] in facts["blocked_communities"])
        }
        return failed, CAUSE_IDS["T02"] if failed else None
    if case_id == "T03":
        failed = set()
        for region, d in facts["regions"].items():
            row_count = d["rules"] * (d["permission_copies"] if not d["distinct"] else 1)
            total_kb = d["header_kb"] + row_count * d["kb_per_row"]
            if total_kb > d["max_file_kb"]:
                failed.add("feature-" + region)
        return failed, CAUSE_IDS["T03"] if failed else None
    if case_id == "T04":
        failed = {
            "queue-" + region
            for region, d in facts["pools"].items()
            if d["batch_jobs"] + d["interactive_reserved"] > d["capacity"]
        }
        return failed, CAUSE_IDS["T04"] if failed else None
    if case_id == "T05":
        failed = {
            "sensor-" + name
            for name, d in facts["agents"].items()
            if d["rollout_enabled"]
            and d["strict_schema"]
            and d["expected_fields"] != facts["producer_fields"]
        }
        return failed, CAUSE_IDS["T05"] if failed else None
    if case_id == "T06":
        failed = {
            "policy-" + region
            for region, item in facts["regions"].items()
            if item["rollout_enabled"]
            and item["parser_version"] < item["required_parser_version"]
            and item["tenant_id"] is None
        }
        failed |= {
            "queue-" + region
            for region, item in facts["pools"].items()
            if item["batch_reservations"] + item["interactive_reservations"] > item["capacity"]
        }
        return failed, CAUSE_IDS["T06"] if failed else None
    if case_id == "T07":
        failed = {
            "feature-" + region
            for region, item in facts["feature_regions"].items()
            if item["header_kb"]
            + item["rules"]
            * (1 if item["distinct"] else item["permission_copies"])
            * item["kb_per_rule"]
            > item["file_limit_kb"]
        }
        failed |= {
            "sensor-" + region
            for region, item in facts["sensors"].items()
            if item["rollout_enabled"]
            and item["strict_schema"]
            and item["expected_fields"] != facts["producer_fields"]
        }
        return failed, CAUSE_IDS["T07"] if failed else None
    raise ValueError(f"Unrecognized case: {case_id}")


def propagate(seeds: set[str], topology: list[dict]) -> set[str]:
    nodes = {x["id"]: x for x in topology}
    if not seeds <= nodes.keys():
        raise ValueError(f"Seeds missing from topology: {seeds - nodes.keys()}")
    for node in topology:
        quorum = node.get("needs_at_least") or {"count": 0, "of": []}
        if not isinstance(quorum.get("count"), int) or not 0 <= quorum["count"] <= len(
            quorum["of"]
        ):
            raise ValueError(f"Invalid quorum for {node['id']}")
        for dep in node.get("needs_all", []) + node.get("needs_any", []) + quorum["of"]:
            if dep not in nodes:
                raise ValueError(f"Unknown dependency {dep}")
    down = set(seeds)
    while True:
        new = set(down)
        for node in topology:
            name = node["id"]
            all_deps = node.get("needs_all", [])
            any_deps = node.get("needs_any", [])
            quorum = node.get("needs_at_least") or {"count": 0, "of": []}
            quorum_unmet = sum(dep not in down for dep in quorum["of"]) < quorum["count"]
            if (
                any(d in down for d in all_deps)
                or (any_deps and all(d in down for d in any_deps))
                or quorum_unmet
            ):
                new.add(name)
        if new == down:
            return down
        down = new


def simulate(case: dict, facts: dict | None = None) -> tuple[set[str], str | None]:
    if facts is None:
        facts = case["facts"]
    seeds, cause = initial_failures(case["id"], facts)
    down = propagate(seeds, facts["topology"])
    return down, cause


def reference_answer(case: dict) -> dict:
    baseline_down, cause = simulate(case)
    if not baseline_down or cause is None:
        raise ValueError(f"{case['id']} does not contain a failure; revise the task")
    possible = []
    for action in case["actions"]:
        new_facts = patch_facts(case["facts"], action)
        after_down, _ = simulate(case, new_facts)
        # A repair must restore EVERY previously failed component and cause NO new outage.
        if not after_down:
            possible.append((action["cost"], action["id"]))
    if not possible:
        raise ValueError(f"{case['id']} has no complete safe intervention")
    possible.sort()
    if len(possible) > 1 and possible[0][0] == possible[1][0]:
        raise ValueError(f"{case['id']} cheapest repair is tied; rewrite candidates")
    return {
        "failed_services": sorted(baseline_down),
        "root_cause": cause,
        "fix_id": possible[0][1],
    }


def reference_audit(case: dict) -> dict:
    """Human-readable counterfactuals for reviewers, not for prompting."""
    down, cause = simulate(case)
    actions = {}
    for action in case["actions"]:
        after, _ = simulate(case, patch_facts(case["facts"], action))
        actions[action["id"]] = {
            "cost": action["cost"],
            "failed_after": sorted(after),
            "full_recovery": not after,
        }
    return {"failed_before": sorted(down), "hypothesis": cause, "actions": actions}
