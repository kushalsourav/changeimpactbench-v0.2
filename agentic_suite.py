"""Versioned synthetic agentic incidents: AG08V4 (strict-cost fix) and AG09--AG12.

These use the established deterministic simulator and bounded JSON tool interface.
The old AG08/AG08V2/AG08V3 sources and their historical hashes are untouched.
All reference answers remain *reviewer-only*: never include them in agent prompts.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

from agentic_v3 import (AgentEnvironment as V3Environment, ProtocolError,
                        parse_tool_call, MAX_TURNS, MAX_TOOL_CALLS,
                        MAX_SIMULATIONS, _f1, digest)
from oracle import initial_failures, reference_answer, reference_audit
from tasks import load_cases

SPECS: dict[str, dict] = {
    'AG08V4': {
        'seed': 'T08', 'version': 'agentic-ag08-v4', 'time': '14:10 UTC',
        'alert': ('At 14:10 UTC, regional settlement degraded during routine changes. '
                  'The global status endpoint appears healthy and an east request path responds.'),
        'observations': [
            '14:12 global-status reports healthy while settlement errors persist',
            '14:13 west reconciler requests time out; root cause not yet established',
            '14:14 global-search continues to respond',
        ],
        'hypotheses': [
            ('H01', 'A single western data-plane synchronization fault'),
            ('H02', 'A shared gateway-wide trust failure'),
            ('H03', 'A single regional gateway trust failure'),
            ('H04', 'Multiple independent local-control failures'),
            ('H05', 'A locally misconfigured quorum rule'),
        ],
    },
    'AG09': {
        'seed': 'T09', 'version': 'agentic-ag09-v1', 'time': '06:20 UTC',
        'alert': ('At 06:20 UTC regional checkout and edge traffic degraded following a failover. '
                  'A dashboard claims a global outage, but one independent edge probe succeeds.'),
        'observations': [
            '06:18 primary regional endpoint became unreachable',
            '06:19 retry traffic increased; origin and scope remain uncertain',
            '06:20 a southern edge transaction succeeded',
        ],
        'hypotheses': [
            ('H01', 'One global name-resolution failure'),
            ('H02', 'Independent regional resolution and capacity-control faults'),
            ('H03', 'One regional capacity-control fault'),
            ('H04', 'Multiple regional capacity-control faults'),
            ('H05', 'One stale regional resolution fault'),
        ],
    },
    'AG10': {
        'seed': 'T10', 'version': 'agentic-ag10-v1', 'time': '09:40 UTC',
        'alert': ('At 09:40 UTC database restore and journal writes degraded during recovery operations. '
                  'An application status indicator is inconsistent with regional symptoms.'),
        'observations': [
            '09:36 restore progress slowed and some snapshot replays failed',
            '09:38 regional journal writes timed out',
            '09:40 not all read paths are unavailable',
        ],
        'hypotheses': [
            ('H01', 'A single journal reserve-capacity fault'),
            ('H02', 'A single leader fencing/index fault'),
            ('H03', 'Two independent replica and journal faults'),
            ('H04', 'A stale presentation cache with no substantive infrastructure defect'),
            ('H05', 'Three interacting local-control failures across recovery paths'),
        ],
    },
    'AG11': {
        'seed': 'T11', 'version': 'agentic-ag11-v1', 'time': '11:25 UTC',
        'alert': ('At 11:25 UTC signing and metadata-backed operations degraded across regions '
                  'during scheduled changes. Regional and central reports disagree.'),
        'observations': [
            '11:21 new signing requests fail in some regions',
            '11:23 one region reports elevated rate-limiting',
            '11:25 central metadata staleness is being investigated',
        ],
        'hypotheses': [
            ('H01', 'A single regional key-compatibility fault'),
            ('H02', 'A single central metadata synchronization fault'),
            ('H03', 'Independent key, capacity, and metadata-control faults'),
            ('H04', 'One global key incompatibility affecting every region'),
            ('H05', 'Capacity and quorum-control faults without a key defect'),
        ],
    },
    'AG12': {
        'seed': 'T12', 'version': 'agentic-ag12-v1', 'time': '16:30 UTC',
        'alert': ('At 16:30 UTC a cross-version rollback was followed by intermittent writes '
                  'and token validation failures. Some independent request paths remain healthy.'),
        'observations': [
            '16:26 a client cohort rolled back',
            '16:28 selected jobs reported authorization errors',
            '16:30 migration and writer versions are under investigation',
        ],
        'hypotheses': [
            ('H01', 'Multiple independent compatibility, timing, and migration faults'),
            ('H02', 'A single migration-control fault'),
            ('H03', 'Two independent local numeric constraint violations'),
            ('H04', 'One regional client incompatibility and one writer mismatch'),
            ('H05', 'One local routing quorum defect'),
        ],
    },
}
TASK_IDS = frozenset(SPECS)


def _spec(task_id: str) -> dict:
    if task_id not in SPECS:
        raise ValueError(f'Unknown agentic scenario: {task_id}')
    return SPECS[task_id]


def source_case(task_id: str) -> dict:
    seed = _spec(task_id)['seed']
    return next(case for case in load_cases({seed}) if case['id'] == seed)


def implementation_hashes() -> dict[str, str]:
    directory = Path(__file__).resolve().parent
    return {name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
            for name in ('agentic_suite.py', 'run_agentic_suite.py',
                         'agentic_v3.py', 'oracle.py')}


def task_catalog(task_id: str) -> dict:
    case = source_case(task_id)
    return {
        'id': task_id, 'title': 'Agentic investigation: ' + case['title'],
        'context': 'Synthetic, versioned tool-use investigation with explicit full, safe, least-cost repair.',
        'services': len(case['facts']['topology']),
        'failed': len(reference_answer(case)['failed_services']),
        'benchmark_version': _spec(task_id)['version'], 'condition': 'agentic',
    }


def agent_prompt(task_id: str) -> str:
    # Share only the frozen public JSON protocol, never the source-case reference.
    from agentic_v3 import agent_prompt as v3_prompt
    text = v3_prompt()
    intro, payload = text.split('\n', 1)
    contract = json.loads(payload)
    spec = _spec(task_id)
    case = source_case(task_id)
    objective = (
        ' Identify EVERY initially unavailable service and the interacting root cause. '
        'Restore ALL initially unavailable services with ONE sandbox repair, create NO new outages, '
        'and select the LOWEST-COST action achieving complete safe recovery. '
        'Partial recovery and unnecessarily costly complete repairs do not meet the objective.'
    )
    contract.update({
        'scenario_id': task_id,
        'scenario_version': spec['version'],
        'alert_summary': spec['alert'] + objective,
        'service_inventory': sorted(node['id'] for node in case['facts']['topology']),
    })
    contract['rules'].append(
        'The strict grader checks that the committed action equals the least-cost complete '
        'safe action, not merely that it restored everything.')
    return intro + '\n' + json.dumps(contract, sort_keys=True, indent=2)


class AgentEnvironment(V3Environment):
    """Reuse the frozen sandbox transitions; replace only public incident surfaces."""
    def __init__(self, task_id: str):
        self.task_id = task_id
        super().__init__(source_case(task_id))

    def execute(self, tool: str, args: dict) -> dict:
        reply = super().execute(tool, args)
        spec = _spec(self.task_id)
        if tool == 'read_alert':
            reply['result'] = {
                'time': spec['time'], 'alert': spec['alert'] + (
                    ' Identify every initially failed service and complete the lowest-cost '
                    'full safe recovery; a partial or unnecessarily costly fix is not successful.'),
                'observations': deepcopy(spec['observations']),
                'hypotheses': [{'id': id_, 'description': meaning}
                               for id_, meaning in spec['hypotheses']],
                'scope': 'Synthetic; reference result withheld',
            }
        elif tool in ('inspect_logs', 'inspect_metrics'):
            reply['result']['timestamp'] = spec['time']
            if tool == 'inspect_logs':
                reply['result']['lines'] = [line.replace('14:10 ', spec['time'] + ' ')
                                            for line in reply['result']['lines']]
        self.steps[-1]['observation'] = deepcopy(reply)
        return reply


def reference_trajectory(task_id: str) -> list[tuple[str, dict]]:
    case = source_case(task_id)
    ref = reference_answer(case)
    direct, _ = initial_failures(case['id'], case['facts'])
    tools: list[tuple[str, dict]] = [('read_alert', {})]
    for name in sorted(direct):
        tools.append(('inspect_config', {'service': name}))
    tools.append(('inspect_dependencies', {'service': sorted(direct)[0]}))
    tools.append(('list_repairs', {}))
    audit = reference_audit(case)['actions']
    partials = [a for a in case['actions'] if not audit[a['id']]['full_recovery']]
    if partials:
        tools.append(('simulate_repair', {'action_id': partials[0]['id']}))
    tools.append(('simulate_repair', {'action_id': ref['fix_id']}))
    tools.append(('apply_repair', {'action_id': ref['fix_id']}))
    observed = [f'EV{i:03d}' for i, (name, _) in enumerate(tools, 1)
                if name in ('inspect_config', 'simulate_repair')]
    tools.append(('submit_diagnosis', {
        **ref, 'evidence_ids': observed,
        'rationale': 'Independent local-check failures and dependency propagation; the least-cost complete safe repair was counterfactually verified.',
    }))
    return tools


def replay_record(record: dict) -> dict:
    """Independent raw provider-turn replay; no trust in cached grade or observations."""
    task_id = record.get('task_id')
    if task_id not in TASK_IDS:
        raise ValueError('Unknown agentic suite task')
    case = source_case(task_id)
    expected = reference_answer(case)
    version = _spec(task_id)['version']
    expected_prompt = agent_prompt(task_id)
    verified = all((
        record.get('benchmark_version') == version,
        record.get('source_hashes') == implementation_hashes(),
        record.get('case_sha256') == digest(case),
        record.get('prompt_sha256') == hashlib.sha256(expected_prompt.encode('utf-8')).hexdigest(),
        record.get('prompt') == expected_prompt,
    ))
    warnings: list[str] = []
    turns, events = record.get('turns'), record.get('trajectory')
    fail = lambda message: {'verified': False, 'warnings': [message], 'grade': None,
                            'unsafe_committed': None, 'committed_action': None,
                            'expected': expected, 'predicted': None}
    if not isinstance(turns, list) or not isinstance(events, list) or len(turns) > MAX_TURNS \
       or len(events) > MAX_TOOL_CALLS or record.get('provider_requests') != len(turns):
        return fail('Invalid agentic-suite provider turn count or missing raw trajectory')
    if record.get('raw_output') != (turns[-1].get('raw_model_output') if turns else ''):
        verified = False
        warnings.append('Final output differs from last provider turn')
    env = AgentEnvironment(task_id)
    protocol_errors = []
    accepted = 0
    for i, item in enumerate(turns, 1):
        if not isinstance(item, dict) or item.get('turn') != i or not isinstance(item.get('raw_model_output'), str):
            return fail(f'Invalid raw provider turn {i}')
        raw = item['raw_model_output']
        if item.get('finish_reason') == 'length' or not raw.strip():
            status = 'incomplete_generation' if item.get('finish_reason') == 'length' else 'empty_generation'
            if i != len(turns) or record.get('status') != status or 'tool' in item or 'protocol_error' in item:
                verified = False
                warnings.append(f'Invalid incomplete turn at {i}')
            continue
        try:
            tool, args = parse_tool_call(raw)
            observed = env.execute(tool, args)
        except ProtocolError as exc:
            reason = str(exc)
            category = ('premature_submit' if reason == 'Commit a sandbox repair before submitting a diagnosis'
                        else 'rejected_tool_call')
            protocol_errors.append({'turn': i, 'reason': reason, 'category': category})
            if item.get('protocol_error') != reason or 'observation' in item or 'tool' in item:
                verified = False
                warnings.append(f'Rejected call mismatch at turn {i}')
        else:
            if item.get('tool') != tool or item.get('arguments') != args or item.get('observation') != observed:
                verified = False
                warnings.append(f'Provider-turn tool response mismatch at {i}')
            if accepted >= len(events):
                verified = False
                warnings.append(f'Missing trajectory event at {i}')
            else:
                event = events[accepted]
                if (event.get('tool') != tool or event.get('arguments') != args or
                    event.get('observation') != observed or event.get('raw_model_output') != raw or
                    event.get('provider_turn') != i):
                    verified = False
                    warnings.append(f'Trajectory mismatch at turn {i}')
            accepted += 1
    if accepted != len(events) or protocol_errors != record.get('protocol_errors'):
        verified = False
        warnings.append('Accepted/rejected event counts do not match raw turns')
    if env.final != record.get('final_diagnosis') or env.committed_effect != record.get('committed_effect') \
       or env.violations != record.get('violations'):
        verified = False
        warnings.append('Final diagnosis, committed state or safety violations differ from replay')
    unsafe = bool(env.committed_effect and env.committed_effect['newly_unavailable'])
    if not verified:
        return {'verified': False, 'warnings': warnings or ['Frozen source or prompt hash mismatch'],
                'grade': None, 'unsafe_committed': None, 'committed_action': None,
                'expected': expected, 'predicted': env.final}
    if record.get('status') != 'completed':
        return {'verified': True, 'warnings': [], 'grade': None,
                'unsafe_committed': unsafe, 'committed_action': env.committed,
                'expected': expected, 'predicted': env.final}
    if env.final is None:
        return fail('Completed record does not contain a submitted diagnosis')
    final = env.final
    f1 = _f1(set(expected['failed_services']), set(final['failed_services']))
    root_ok = final['root_cause'] == expected['root_cause']
    fix_ok = final['fix_id'] == expected['fix_id']
    effect = env.committed_effect or {}
    safe = not effect.get('newly_unavailable') and 'unsafe_committed_repair' not in env.violations
    complete = bool(effect) and not effect.get('unavailable_after')
    citations = set(final['evidence_ids'])
    cited = [step for step in env.steps if step['observation']['event_id'] in citations]
    provenance_ok = len(cited) == len(citations) and len(cited) >= 2
    supporting = sum(step['tool'] in ('inspect_config','inspect_metrics','inspect_logs','simulate_repair')
                     for step in cited)
    evidence_points = (10 if provenance_ok and supporting >= 2 else
                       5 if provenance_ok and supporting >= 1 else 0)
    premature = sum(error['category'] == 'premature_submit' for error in protocol_errors)
    other_rejected = sum(error['category'] != 'premature_submit' for error in protocol_errors)
    procedure_points = max(0, 10 - 2 * premature - 5 * other_rejected)
    if env.violations:
        procedure_points = 0
    strict = (
        set(final['failed_services']) == set(expected['failed_services']) and root_ok and fix_ok
        and env.committed == expected['fix_id'] and safe and complete
        and not env.violations and not other_rejected
    )
    score = round(.20 * f1 + .20 * int(root_ok) + .40 * int(safe and complete)
                  + .10 * evidence_points / 10 + .10 * procedure_points / 10, 5)
    sims = [step['arguments']['action_id'] for step in env.steps if step['tool'] == 'simulate_repair']
    grade = {
        'pass': strict, 'strict_pass': strict, 'score': score, 'affected_f1': round(f1, 5),
        'root_correct': root_ok, 'fix_correct': fix_ok, 'format_valid': True,
        'recovery_safe': safe, 'recovery_success': complete, 'unsafe_commit': not safe,
        'committed_action': env.committed, 'evidence_score': evidence_points,
        'evidence_review': 'automated citation provenance only; human semantic review pending',
        'procedure_score': procedure_points, 'tool_calls': len(events),
        'simulation_calls': env.simulations, 'protocol_errors': protocol_errors,
        'violations': list(env.violations) + [error['category'] for error in protocol_errors],
        'commit_was_simulated': env.committed in sims, 'counterfactual_checks': len(sims),
        'repair_safety_note': ('Agent used sandbox counterfactual checks.' if sims
                               else 'Simulation not requested; no automatic penalty.'),
    }
    return {'verified': True, 'warnings': [], 'grade': grade, 'unsafe_committed': unsafe,
            'committed_action': env.committed, 'expected': expected, 'predicted': final}
