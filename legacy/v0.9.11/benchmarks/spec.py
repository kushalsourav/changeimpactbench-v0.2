"""Source-grounded public incident reconstructions; no historical agent imports.

Only public alert, neutral hypotheses, and experiment controls are exposed to the
model. Original seeded facts, repair consequences and reference answers remain
restricted to the sandbox and independent evaluator.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from hashlib import sha256
import json
from typing import Any
from oracle import reference_answer, reference_audit, initial_failures
from tasks import load_cases

@dataclass(frozen=True)
class TaskSpec:
    id: str
    version: str
    seed: str
    time: str
    alert: str
    observations: tuple[str, ...]
    hypotheses: tuple[tuple[str, str], ...]
    max_model_calls: int = 48
    max_tools: int = 47
    max_simulations: int = 3
    source_url: str = ""
    documented_facts: tuple[str, ...] = ()
    model_assumptions: tuple[str, ...] = ()

def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)

def digest(obj: Any) -> str:
    return sha256(canonical(obj).encode('utf-8')).hexdigest()

_REGISTRY_RAW = json.loads(Path(__file__).with_name("public_sources.json").read_text(encoding="utf-8"))

REGISTRY: dict[str, TaskSpec] = {
    task_id: TaskSpec(id=task_id,
        version=raw["version"],
        seed=raw['seed'], time=raw['time'], alert=raw['alert'],
        observations=tuple(raw['observations']),
        hypotheses=tuple(tuple(x) for x in raw['hypotheses']),
        source_url=raw['source_url'],
        documented_facts=tuple(raw['documented_facts']),
        model_assumptions=tuple(raw['model_assumptions']))
    for task_id,raw in _REGISTRY_RAW.items()
}

def get_spec(task_id: str) -> TaskSpec:
    try:
        return REGISTRY[task_id]
    except KeyError as exc:
        raise ValueError(f'Unknown source-grounded incident: {task_id}') from exc

def source_case(task_id: str) -> dict:
    seed = get_spec(task_id).seed
    return next(case for case in load_cases({seed}) if case['id'] == seed)

def reference_trajectory(task_id: str) -> list[tuple[str, dict]]:
    """Reviewer-side deterministic sequence for OFFLINE tests, never provider evidence."""
    case = source_case(task_id)
    reference = reference_answer(case)
    direct, _ = initial_failures(case['id'], case['facts'])
    result = [('read_alert', {}), ('scan_service_health', {})]
    for service in sorted(direct):
        result.append(('inspect_config', {'service': service}))
    result.append(('inspect_dependencies', {'service': sorted(direct)[0]}))
    result.append(('list_repairs', {}))
    outcomes = reference_audit(case)['actions']
    partials = [a for a in case['actions'] if not outcomes[a['id']]['full_recovery']]
    cause_id = reference['root_cause']
    description = next(desc for label, desc in get_spec(task_id).hypotheses if label == cause_id)
    evidence_before = [f'EV{i:03d}' for i, (name, _) in enumerate(result, 1)
                       if name in ('inspect_config', 'inspect_dependencies', 'scan_service_health')]
    result.append(('prepare_repair', {
        'failed_services': reference['failed_services'],
        'hypothesized_root_cause_id': cause_id,
        'repair_instructions': f'Investigated the independent failure paths with direct local checks. Proposed cause: {description}. Compare candidates for full safe recovery; choose the least-cost repair and verify the result before final submission.',
        'evidence_ids': evidence_before,
    }))
    if partials:
        result.append(('simulate_repair', {'action_id': partials[0]['id']}))
    result.append(('simulate_repair', {'action_id': reference['fix_id']}))
    result.append(('apply_repair', {'action_id': reference['fix_id']}))
    evidence = [f'EV{i:03d}' for i, (name, _) in enumerate(result, 1)
                if name in ('inspect_config', 'simulate_repair')]
    cause_id = reference['root_cause']
    description = next(desc for label, desc in get_spec(task_id).hypotheses if label == cause_id)
    result.append(('submit_diagnosis', {
        'failed_services': reference['failed_services'],
        'root_cause_id': cause_id,
        'root_cause_explanation': f'{description}. Verified through direct local checks and downstream dependency evidence.',
        'fix_id': reference['fix_id'], 'evidence_ids': evidence,
        'rationale': 'Independent local-check faults and cascading dependencies; the lowest-cost complete safe repair was checked with counterfactual simulation.'
    }))
    return result
