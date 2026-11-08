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

# The six original V6 counterfactual fixtures are the only active dataset.
# Do not present source/postmortem metadata to the agent; keep it reviewer-only.
V6_FIXTURES = Path(__file__).with_name('v6_fixtures') / 'counterfactual'
V6_REGISTRY: dict[str, TaskSpec] = {}
for _path in sorted(V6_FIXTURES.glob('RW*.json')):
    _public = json.loads(_path.read_text(encoding='utf-8'))['task']
    _task_id = _path.stem + 'V6CF'
    V6_REGISTRY[_task_id] = TaskSpec(
        id=_task_id, version='agentic-v6-counterfactual-2', seed=_path.stem,
        time=_public['time'], alert=_public['alert'], observations=(),
        hypotheses=tuple((h['id'], h['description']) for h in _public['hypotheses']),
        max_model_calls=_public['max_turns'], max_tools=_public['max_tools'],
        max_simulations=_public['max_simulations'],
        source_url='', documented_facts=(),
        model_assumptions=('Entirely synthetic; deterministic counterfactual environment',),
    )


def synthetic_task(task_id: str) -> bool:
    return task_id in V6_REGISTRY


def fixture_path(task_id: str) -> Path:
    return V6_FIXTURES / (get_spec(task_id).seed + '.json')


def service_codes(task_id: str) -> dict[str, str]:
    fixture = json.loads(fixture_path(task_id).read_text(encoding='utf-8'))
    return {item['role']: item['service_code'] for item in fixture['task']['public_inventory']}


def get_spec(task_id: str) -> TaskSpec:
    try:
        return V6_REGISTRY[task_id]
    except KeyError as exc:
        raise ValueError(f'Unknown V6 counterfactual incident: {task_id}') from exc


def source_case(task_id: str) -> dict:
    return json.loads(fixture_path(task_id).read_text(encoding='utf-8'))['case']


def reference_path(task_id: str) -> Path:
    return Path(__file__).resolve().parent.parent / 'reference' / 'v6-counterfactual' / (get_spec(task_id).seed + '.json')


def reviewer_source(task_id: str) -> dict:
    case = source_case(task_id)
    return {
        'original_source_name': case['title'],
        'source_url': case.get('provenance', {}).get('source_url', ''),
        'documented_facts': case.get('provenance', {}).get('documented_facts', []),
        'reconstructed_elements': case.get('provenance', {}).get('reconstructed_elements', []),
        'attribution_note': ('Fully synthetic counterfactual inspired by an operator-published incident. '
                             'No simulator state or metric is original production telemetry.'),
    }


def reference_trajectory(task_id: str) -> list[tuple[str, dict]]:
    """Reviewer-side deterministic sequence for OFFLINE tests, never provider evidence."""
    case = source_case(task_id)
    reference = reference_answer(case)
    direct, _ = initial_failures(case['id'], case['facts'])
    result = [('read_alert', {}), ('scan_service_health', {})]
    codes = service_codes(task_id)
    for service in sorted(n['id'] for n in case['facts']['topology']):
        result.append(('inspect_metrics', {'service': codes.get(service, service)}))
        if service in direct:
            result.append(('inspect_config', {'service': codes.get(service, service)}))
    result.append(('inspect_dependencies', {'service': codes.get(sorted(direct)[0], sorted(direct)[0])}))
    result.append(('list_repairs', {}))
    outcomes = reference_audit(case)['actions']
    partials = [a for a in case['actions'] if not outcomes[a['id']]['full_recovery']]
    cause_id = reference['root_cause']
    description = next(desc for label, desc in get_spec(task_id).hypotheses if label == cause_id)
    evidence_before = [f'EV{i:03d}' for i, (name, _) in enumerate(result, 1)
                       if name in ('inspect_config', 'inspect_dependencies', 'scan_service_health')]
    result.append(('prepare_repair', {
        'failed_services': sorted(codes.get(n,n) for n in reference['failed_services']),
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
        'failed_services': sorted(codes.get(n,n) for n in reference['failed_services']),
        'root_cause_id': cause_id,
        'root_cause_explanation': f'{description}. Verified through direct local checks and downstream dependency evidence.',
        'fix_id': reference['fix_id'], 'evidence_ids': evidence,
        'rationale': 'Independent local-check faults and cascading dependencies; the lowest-cost complete safe repair was checked with counterfactual simulation.'
    }))
    return result
