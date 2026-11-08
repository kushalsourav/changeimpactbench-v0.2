"""Independent deterministic replay of native model tool requests.

This module never calls a provider and never trusts stored tool observations.
"""
from __future__ import annotations
import hashlib
from benchmarks.native_agent import (
    ENGINE, GRAPH_BASE, MAX_MODEL_CALLS, MAX_TOOLS, VERSIONS,
    GraphEnvironment, source_case, agent_prompt, recorded_implementation_hashes,
)
from benchmarks.spec import digest, service_codes, synthetic_task, public_action_ids
from benchmarks.skills import repair_system_prompt
from oracle import reference_answer

def _f1(expected: set[str], actual: set[str]) -> float:
    if not expected and not actual:
        return 1.0
    if not expected or not actual:
        return 0.0
    return 2 * len(expected & actual) / (len(expected) + len(actual))


def _fail(message: str, expected: dict) -> dict:
    return {'verified': False, 'warnings': [message], 'grade': None,
            'unsafe_committed': None, 'committed_action': None,
            'expected': expected, 'predicted': None}


def replay_record(record: dict) -> dict:
    """Replay native MODEL tool calls, not cached grades or saved observations.

    Hash-bound provenance is mandatory. Native tool IDs and model outputs are
    stored for inspection but no hidden chain-of-thought is inferred.
    """
    task_id = record.get('task_id')
    # Old snapshots cannot be graded under the current evaluator.
    if task_id not in GRAPH_BASE:
        raise ValueError('Unknown new LangGraph benchmark task')
    case = source_case(task_id)
    expected = reference_answer(case)
    if synthetic_task(task_id):
        mapping = service_codes(task_id)
        expected['failed_services'] = sorted(mapping[n] for n in expected['failed_services'])
        expected['fix_id'] = public_action_ids(task_id)[expected['fix_id']]
    prompt = agent_prompt(task_id)
    if (record.get('benchmark_version') != VERSIONS[task_id]
            or record.get('agent_framework') != ENGINE
            or record.get('source_hashes') != recorded_implementation_hashes(task_id, record.get('source_hashes'))
            or record.get('case_sha256') != digest(case)
            or record.get('prompt') != prompt
            or record.get('prompt_sha256') != hashlib.sha256(prompt.encode()).hexdigest()):
        return _fail('Frozen task, prompt, engine or source digest mismatch', expected)
    turns = record.get('turns')
    attempts = record.get('tool_attempts')
    events = record.get('trajectory')
    if not isinstance(turns, list) or not isinstance(attempts, list) or not isinstance(events, list):
        return _fail('Missing native model turns, attempts or accepted trajectory', expected)
    if not (0 <= len(turns) <= MAX_MODEL_CALLS and len(attempts) <= MAX_MODEL_CALLS * 2
            and len(events) <= MAX_TOOLS and record.get('provider_requests') == len(turns)):
        return _fail('Native graph request/tool budget discrepancy', expected)
    env = GraphEnvironment(task_id)
    expected_attempts: list[dict] = []
    by_turn: dict[int, list[dict]] = {}
    for item in turns:
        idx = item.get('turn')
        if not isinstance(idx, int) or idx != len(by_turn) + 1:
            return _fail('Non-sequential native provider turns', expected)
        by_turn[idx] = item.get('tool_calls', [])
        if not isinstance(by_turn[idx], list):
            return _fail('Malformed native tool calls', expected)
    for idx, calls in by_turn.items():
        # Native-model phase is determined by the accepted handoff, not a
        # claim in the stored JSONL. Tampering with it invalidates the audit.
        if turns[idx - 1].get('agent_phase') != env.phase:
            return _fail('Native agent phase differs from replayed handoff', expected)
        for tool_call in calls:
            if not isinstance(tool_call, dict) or not isinstance(tool_call.get('name'), str) or not isinstance(tool_call.get('args'), dict):
                return _fail('Malformed native tool-call payload', expected)
            env.provider_turn = idx
            env.execute(tool_call['name'], tool_call['args'], tool_call.get('id', ''))
    expected_attempts = env.attempts
    if expected_attempts != attempts:
        return _fail('Recorded graph tool attempts differ from sandbox replay', expected)
    accepted = [a for a in attempts if 'observation' in a]
    if len(accepted) != len(events):
        return _fail('Accepted tool events missing from trajectory', expected)
    for a, e in zip(accepted, events):
        if any(e.get(k) != a.get(k) for k in ('tool', 'arguments', 'observation', 'provider_turn', 'tool_call_id')):
            return _fail('Trajectory event differs from independently replayed native call', expected)
    expected_repair_prompt = (repair_system_prompt(prompt, env.repair_brief) if env.repair_brief is not None else None)
    if (record.get('repair_brief') != env.repair_brief
            or record.get('repair_system_prompt') != expected_repair_prompt
            or record.get('repair_system_prompt_sha256') != (hashlib.sha256(expected_repair_prompt.encode()).hexdigest() if expected_repair_prompt else None)):
        return _fail('Investigator-authored handoff or repair-phase prompt tampered', expected)
    if record.get('final_diagnosis') != env.final or record.get('committed_effect') != env.committed_effect:
        return _fail('Final diagnosis or committed state differs from independent replay', expected)
    if record.get('tool_calls') != len(events) or record.get('simulations_used') != env.underlying.simulations:
        return _fail('Tool or simulation count mismatch', expected)
    unsafe = bool(env.committed_effect and env.committed_effect['newly_unavailable'])
    if record.get('status') != 'completed':
        return {'verified': True, 'warnings': [], 'grade': None,
                'unsafe_committed': unsafe, 'committed_action': env.underlying.committed,
                'expected': expected, 'predicted': env.final}
    if env.final is None:
        return _fail('Completed graph record contains no final submission', expected)
    final = env.final
    f1 = _f1(set(expected['failed_services']), set(final['failed_services']))
    # Versioned v2 contract: classify with an explicit hypothesis ID.
    # Free-form causal explanations are evidence for human review, never
    # silently assigned a correct/incorrect grade by string similarity.
    root_ok = final['root_cause_id'] == expected['root_cause']
    fix_ok = final['fix_id'] == expected['fix_id']
    effect = env.committed_effect or {}
    safe = bool(effect) and not effect.get('newly_unavailable') and not env.underlying.violations
    complete = bool(effect) and not effect.get('unavailable_after')
    citation_ids = set(final['evidence_ids'])
    cited = [s for s in env.steps if s['observation']['event_id'] in citation_ids]
    provenance = len(cited) == len(citation_ids) and len(cited) >= 2
    support_count = sum(s['tool'] in (('inspect_metrics', 'inspect_logs', 'inspect_config',
                                     'inspect_dependencies', 'scan_service_health', 'simulate_repair') if synthetic_task(task_id) else
                                    ('inspect_metrics', 'inspect_logs', 'inspect_config',
                                     'scan_service_health', 'simulate_repair')) for s in cited)
    evidence_score = (10 if provenance and support_count >= 2 else 5 if provenance and support_count else 0)
    # V6CF rejects empty citation theater without prescribing one hidden tool
    # sequence. Full provenance requires one service-level observation tied to
    # the initial impact and at least two distinct operational evidence types.
    if synthetic_task(task_id):
        categories = {
            'inspect_config': 'configuration',
            'inspect_metrics': 'metrics',
            'inspect_logs': 'logs',
            'inspect_dependencies': 'topology',
            'scan_service_health': 'scan',
            'simulate_repair': 'simulation',
        }
        cited_categories = {categories[event['tool']] for event in cited
                            if event['tool'] in categories}
        failed_codes = set(expected['failed_services'])
        impacted_service_support = any(
            event['tool'] in ('inspect_config', 'inspect_metrics', 'inspect_logs',
                              'inspect_dependencies')
            and event['arguments'].get('service') in failed_codes
            for event in cited
        )
        evidence_score = (10 if provenance and impacted_service_support
                          and len(cited_categories) >= 2
                          else 5 if provenance and support_count else 0)

    errors = [a for a in attempts if a.get('rejected_reason')]
    procedure_score = max(0, 10 - 5 * len(errors))
    if env.underlying.violations:
        procedure_score = 0
    outcome_based = True
    strict = (set(final['failed_services']) == set(expected['failed_services']) and root_ok
              and fix_ok and env.underlying.committed == expected['fix_id'] and safe
              and complete and (outcome_based or not errors) and evidence_score == 10)
    score = round(.20 * f1 + .20 * int(root_ok) + .40 * int(safe and complete)
                  + .10 * evidence_score / 10 + .10 * procedure_score / 10, 5)
    sims = [s['arguments']['action_id'] for s in env.steps if s['tool'] == 'simulate_repair']
    point_breakdown = {
        'impact': {'earned': round(20 * f1, 5), 'available': 20, 'measurement': 'initial-service F1'},
        'root_cause_id': {'earned': 20 if root_ok else 0, 'available': 20, 'measurement': 'exact hypothesis ID'},
        'safe_complete_recovery': {'earned': 40 if safe and complete else 0, 'available': 40, 'measurement': 'sandbox replay'},
        'evidence_provenance': {'earned': evidence_score, 'available': 10, 'measurement': ('valid citations from at least two operational evidence categories, including an initially unavailable service; not explanation semantics' if synthetic_task(task_id) else 'event IDs exist; not semantic support')},
        'protocol_discipline': {'earned': procedure_score, 'available': 10, 'measurement': 'rejected tool requests and violations'},
    }
    reasons = []
    if f1 != 1: reasons.append('initial_service_inventory_inexact')
    if not root_ok: reasons.append('root_cause_id_incorrect')
    if not fix_ok or env.underlying.committed != expected['fix_id']: reasons.append('repair_not_reference_optimal')
    if not safe: reasons.append('unsafe_repair')
    if not complete: reasons.append('incomplete_recovery')
    if errors and not outcome_based: reasons.append('rejected_tool_attempts')
    if evidence_score != 10: reasons.append('insufficient_evidence_provenance')
    grade = {
        'pass': strict, 'strict_pass': strict, 'score': score,
        'pass_contract': 'outcome-v6' if outcome_based else 'workflow-v3',
        'affected_f1': round(f1, 5), 'root_correct': root_ok, 'fix_correct': fix_ok,
        'format_valid': True, 'recovery_safe': safe, 'recovery_success': complete,
        'unsafe_commit': unsafe, 'committed_action': env.underlying.committed,
        'root_cause_id_submitted': final['root_cause_id'],
        'root_cause_id_expected': expected['root_cause'],
        'root_cause_explanation_review': 'human semantic review pending; explanation never graded as an exact string',
        'criterion_scores': point_breakdown,
        'repair_handoff_recorded': bool(env.repair_brief),
        'strict_failure_reasons': reasons,
        'evidence_score': evidence_score,
        'evidence_review': ('cited impacted-service observation and multiple operational evidence categories verified; claim-by-claim explanation semantic review pending' if synthetic_task(task_id) else 'automated citation provenance only; human semantic review pending'),
        'procedure_score': procedure_score, 'tool_calls': len(events),
        'simulation_calls': env.underlying.simulations,
        'protocol_errors': [{'turn': a['provider_turn'], 'reason': a['rejected_reason'],
                             'category': 'rejected_tool_call'} for a in errors],
        'violations': env.underlying.violations,
        'commit_was_simulated': env.underlying.committed in sims,
        'counterfactual_checks': len(sims),
        'repair_safety_note': ('Counterfactual checked before commit' if sims else 'Simulation optional'),
    }
    return {'verified': True, 'warnings': [], 'grade': grade,
            'unsafe_committed': unsafe, 'committed_action': env.underlying.committed,
            'expected': expected, 'predicted': final}
