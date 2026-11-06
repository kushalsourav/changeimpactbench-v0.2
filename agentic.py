"""AG08: offline, deterministic tool-use incident evaluation. No cloud mutations.

The experiment model sees only ``agent_prompt`` plus exact ``execute`` observations.
Only the evaluator can access the T08 oracle. Every recorded tool observation is
recomputed on replay, making tampered trajectories unverified rather than scored.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from oracle import initial_failures, patch_facts, reference_answer, simulate
from tasks import load_cases

VERSION = 'agentic-ag08-v1'
TASK_ID = 'AG08'
MAX_TURNS = 24
MAX_TOOL_CALLS = 23
MAX_SIMULATIONS = 3
TOOL_NAMES = (
    'read_alert', 'inspect_logs', 'inspect_metrics', 'inspect_config',
    'inspect_dependencies', 'list_repairs', 'simulate_repair',
    'apply_repair', 'submit_diagnosis',
)
SERVICE_TOOLS = {'inspect_logs', 'inspect_metrics', 'inspect_config', 'inspect_dependencies'}
ACTION_TOOLS = {'simulate_repair', 'apply_repair'}


def implementation_hashes() -> dict[str, str]:
    base = Path(__file__).resolve().parent
    return {
        name: hashlib.sha256((base / name).read_bytes()).hexdigest()
        for name in ('agentic.py', 'oracle.py', 'run_agentic.py')
    }


def source_case() -> dict:
    return next(c for c in load_cases({'T08'}) if c['id'] == 'T08')


def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(obj: Any) -> str:
    return hashlib.sha256(canonical(obj).encode('utf-8')).hexdigest()


def task_catalog() -> dict:
    case = source_case()
    return {'id': TASK_ID, 'title': 'Agentic investigation: ' + case['title'],
            'context': 'Incremental evidence and sandbox-only repair. No golden answer in the agent prompt.',
            'services': len(case['facts']['topology']),
            'failed': len(reference_answer(case)['failed_services']),
            'benchmark_version': VERSION, 'condition': 'agentic'}


def agent_prompt() -> str:
    case = source_case()
    inventory = sorted(n['id'] for n in case['facts']['topology'])
    contract = {
        'scenario_id': TASK_ID,
        'scenario_version': VERSION,
        'alert_summary': case['context'],
        'service_inventory': inventory,
        'tool_protocol': 'Return EXACTLY one JSON object per turn: {"tool":"tool_name","arguments":{...}}. No prose, markdown or additional fields.',
        'available_tools': {
            'read_alert': {},
            'inspect_logs': {'service': 'service-id'},
            'inspect_metrics': {'service': 'service-id'},
            'inspect_config': {'service': 'service-id'},
            'inspect_dependencies': {'service': 'service-id'},
            'list_repairs': {},
            'simulate_repair': {'action_id': 'Axx'},
            'apply_repair': {'action_id': 'Axx'},
            'submit_diagnosis': {'failed_services': ['service-id'], 'root_cause': 'Hxx',
                                 'fix_id': 'Axx', 'evidence_ids': ['EV001', 'EV002'],
                                 'rationale': 'Short decision rationale'},
        },
        'rules': [
            'All systems, logs and effects are fictional and simulated; tools cannot change real infrastructure.',
            'Propagation rule: a service fails if its own local check fails, ANY needs_all dependency is down, ALL nonempty needs_any dependencies are down, or fewer than needs_at_least.count dependencies from needs_at_least.of are healthy. Recompute to a fixed point. Empty dependency lists impose no condition.',
            'Local checks are declarative: all / any / not and left,op,right comparisons (eq,ne,gt,ge,lt,le). Operands are path, literal, sum or product; numeric gt/lt are strict. Never invent implicit failure rules.',
            'Investigate before acting. inspect_config returns a local rule and factual inputs, not a health oracle.',
            'inspect_dependencies returns only local neighbors; inspect_metrics returns one service health observation.',
            'simulate_repair is read-only, has a limited budget, and returns observable summary effects, NOT the ground truth answer.',
            'A repair is committed ONLY by apply_repair and may be unsafe. You may commit at most once.',
            'You must call submit_diagnosis AFTER your repair commitment. Cite evidence IDs of actually observed tools.',
            'Report the failed service set from the INITIAL incident, not the repaired state.',
            'Your answer must be grounded in observable evidence. A false citation is not valid.',
            f'Budget: at most {MAX_TURNS} total turns, {MAX_TOOL_CALLS} tool invocations, and {MAX_SIMULATIONS} simulated repairs.',
            'An incomplete generation or provider failure is recorded separately from wrong diagnosis.',
        ],
    }
    return ('You are a reliability-response agent in an isolated evaluation. '
            'The following JSON defines your tools and boundaries. You can ONLY interact using JSON tool calls.\n'
            + json.dumps(contract, sort_keys=True, indent=2))


class ProtocolError(ValueError):
    pass


def parse_tool_call(raw: str) -> tuple[str, dict]:
    try:
        value = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ProtocolError('A turn must be one valid JSON object') from exc
    if not isinstance(value, dict) or set(value) != {'tool', 'arguments'}:
        raise ProtocolError('Tool turns need exactly tool and arguments fields')
    tool, args = value['tool'], value['arguments']
    if tool not in TOOL_NAMES or not isinstance(args, dict):
        raise ProtocolError('Unknown tool or malformed arguments')
    return tool, args


class AgentEnvironment:
    def __init__(self, case: dict | None = None):
        self.case = deepcopy(case or source_case())
        self.original_facts = deepcopy(self.case['facts'])
        self.facts = deepcopy(self.original_facts)
        self.original_down, _ = simulate(self.case)
        self.steps: list[dict] = []
        self.simulations = 0
        self.committed: str | None = None
        self.committed_effect: dict | None = None
        self.final: dict | None = None
        self.closed = False
        self.violations: list[str] = []
        self.nodes = {n['id']: n for n in self.facts['topology']}
        self.actions = {a['id']: a for a in self.case['actions']}

    def _arguments(self, tool: str, args: dict) -> None:
        expected = (set() if tool in ('read_alert', 'list_repairs') else
                    {'service'} if tool in SERVICE_TOOLS else
                    {'action_id'} if tool in ACTION_TOOLS else
                    {'failed_services', 'root_cause', 'fix_id', 'evidence_ids', 'rationale'})
        if set(args) != expected:
            raise ProtocolError(f'{tool} expects exactly {sorted(expected)}')
        if tool in SERVICE_TOOLS and (not isinstance(args['service'], str)
                                     or args['service'] not in self.nodes):
            raise ProtocolError('Unknown service ID')
        if tool in ACTION_TOOLS and (not isinstance(args['action_id'], str)
                                    or args['action_id'] not in self.actions):
            raise ProtocolError('Unknown repair ID')

    def _local_details(self, service: str) -> dict:
        entries = [r for r in self.facts['local_rules'] if r['service'] == service]
        if not entries:
            return {'configured_local_check': False, 'rule': None, 'referenced_values': {}}
        rule = entries[0]['when']
        paths: list[tuple[str, ...]] = []
        def walk(v: Any) -> None:
            if isinstance(v, dict):
                if isinstance(v.get('path'), list):
                    paths.append(tuple(v['path']))
                for sub in v.values():
                    walk(sub)
            elif isinstance(v, list):
                for sub in v:
                    walk(sub)
        walk(rule)
        fields = {}
        for path in sorted(set(paths)):
            item = self.facts
            for name in path:
                item = item[name]
            fields['.'.join(path)] = item
        return {'configured_local_check': True, 'rule': deepcopy(rule),
                'referenced_values': fields}

    def execute(self, tool: str, args: dict) -> dict:
        """Execute one validated sandbox tool and return exactly what the model sees."""
        if self.closed or len(self.steps) >= MAX_TOOL_CALLS:
            raise ProtocolError('Episode is closed or tool budget exceeded')
        self._arguments(tool, args)
        event_id = f'EV{len(self.steps) + 1:03d}'
        before_down, _ = simulate(self.case, self.facts)
        direct, _ = initial_failures(self.case['id'], self.facts)
        if tool == 'read_alert':
            observation = {'time': '14:10 UTC', 'alert': self.case['context'],
                           'observations': self.case['facts'].get('observations', []),
                           'hypotheses': self.case['hypotheses'],
                           'scope': 'Synthetic, incident state at 14:10 UTC'}
        elif tool == 'list_repairs':
            observation = {'candidate_repairs': [
                {k: deepcopy(v) for k, v in a.items() if k in ('id', 'cost', 'meaning', 'changes')}
                for a in self.case['actions']]}
        elif tool in SERVICE_TOOLS:
            name = args['service']
            node = self.nodes[name]
            if tool == 'inspect_config':
                observation = {'service': name, **self._local_details(name)}
            elif tool == 'inspect_dependencies':
                upstream = {k: deepcopy(v) for k, v in node.items() if k != 'id'}
                consumers = [other['id'] for other in self.facts['topology']
                             if name in (other.get('needs_all', []) + other.get('needs_any', [])
                                         + (other.get('needs_at_least') or {}).get('of', []))]
                # Local one-hop neighborhood: enough to follow cascades without
                # handing the agent the entire topology or failure set at once.
                consumer_rules = {
                    consumer: {k: deepcopy(v) for k, v in self.nodes[consumer].items() if k != 'id'}
                    for consumer in consumers
                }
                observation = {'service': name, 'upstream': upstream,
                               'direct_consumers': consumers,
                               'consumer_dependency_rules': consumer_rules}
            elif tool == 'inspect_metrics':
                observation = {'service': name, 'timestamp': '14:10 UTC',
                               'health_probe': 'unavailable' if name in before_down else 'healthy',
                               'synthetic_request_errors_per_minute': 60 if name in before_down else 0}
            else:
                observation = {'service': name, 'timestamp': '14:10 UTC',
                               'lines': [f'14:10 {name} '
                                         + ('local validation rejected request' if name in direct
                                            else 'upstream dependency unavailable' if name in before_down
                                            else 'health probe passing')]}
        elif tool == 'simulate_repair':
            if self.simulations >= MAX_SIMULATIONS:
                raise ProtocolError('Simulation-call budget exceeded')
            self.simulations += 1
            action = self.actions[args['action_id']]
            changed = patch_facts(self.facts, action)
            after_down, _ = simulate(self.case, changed)
            observation = {'action_id': action['id'], 'cost': action['cost'],
                           'unavailable_after_count': len(after_down),
                           'restored_count': len(before_down - after_down),
                           'newly_unavailable_count': len(after_down - before_down),
                           'simulated_only': True,
                           'state_unchanged': True}
        elif tool == 'apply_repair':
            if self.committed is not None:
                self.violations.append('attempted_second_commit')
                raise ProtocolError('Only one committed repair is allowed')
            action = self.actions[args['action_id']]
            self.facts = patch_facts(self.facts, action)
            after_down, _ = simulate(self.case, self.facts)
            self.committed = action['id']
            self.committed_effect = {'action_id': action['id'], 'unavailable_after': sorted(after_down),
                                     'newly_unavailable': sorted(after_down - before_down),
                                     'restored': sorted(before_down - after_down),
                                     'facts_sha256': digest(self.facts)}
            observation = {'action_id': action['id'], 'committed_in_sandbox': True,
                           'unavailable_after_count': len(after_down),
                           'newly_unavailable_count': len(after_down - before_down),
                           'restored_count': len(before_down - after_down),
                           'synthetic_only': True}
            if after_down - before_down:
                self.violations.append('unsafe_committed_repair')
        else:
            if self.committed is None:
                raise ProtocolError('Commit a sandbox repair before submitting a diagnosis')
            services = args['failed_services']
            ids = args['evidence_ids']
            if (not isinstance(services, list) or not all(isinstance(x, str) for x in services)
                or len(set(services)) != len(services) or any(s not in self.nodes for s in services)
                or not isinstance(args['root_cause'], str)
                or not isinstance(args['fix_id'], str)
                or not isinstance(ids, list) or not all(isinstance(x, str) for x in ids)
                or len(set(ids)) != len(ids) or not isinstance(args['rationale'], str)
                or len(args['rationale']) > 2000):
                raise ProtocolError('Invalid final diagnosis fields or unknown service')
            self.final = deepcopy(args)
            self.closed = True
            observation = {'received': True, 'final_status': 'submitted_for_independent_grading'}
        reply = {'event_id': event_id, 'tool': tool, 'result': observation}
        self.steps.append({'tool': tool, 'arguments': deepcopy(args), 'observation': deepcopy(reply)})
        return reply


def reference_trajectory() -> list[tuple[str, dict]]:
    """Offline reference; never handed to the model as an example."""
    ref = reference_answer(source_case())
    return [
        ('read_alert', {}),
        ('inspect_config', {'service': 'gateway-north'}),
        ('inspect_config', {'service': 'ledger-west'}),
        ('inspect_dependencies', {'service': 'api-north'}),
        ('list_repairs', {}),
        ('simulate_repair', {'action_id': 'A04'}),
        ('simulate_repair', {'action_id': ref['fix_id']}),
        ('apply_repair', {'action_id': ref['fix_id']}),
        ('submit_diagnosis', {**ref, 'evidence_ids': ['EV002', 'EV003', 'EV007'],
                              'rationale': 'Both direct constraints failed; the verified repair restores without damaging east.'}),
    ]


def _f1(expected: set[str], actual: set[str]) -> float:
    if not expected and not actual:
        return 1.0
    if not actual or not expected:
        return 0.0
    match = len(expected & actual)
    return (2 * match / (len(expected) + len(actual)))


def replay_record(record: dict) -> dict:
    """Independent replay and grade; do not trust cached scores or tool results."""
    prompt_hash = hashlib.sha256(agent_prompt().encode('utf-8')).hexdigest()
    case_hash = digest(source_case())
    verified = (record.get('source_hashes') == implementation_hashes()
                and record.get('prompt_sha256') == prompt_hash
                and record.get('case_sha256') == case_hash
                and record.get('benchmark_version') == VERSION
                and record.get('task_id') == TASK_ID)
    env = AgentEnvironment()
    warnings: list[str] = []
    events = record.get('trajectory', [])
    if not isinstance(events, list) or len(events) > MAX_TOOL_CALLS:
        return {'verified': False, 'warnings': ['Invalid trajectory count'], 'grade': None,
                'expected': reference_answer(source_case()), 'predicted': None}
    for i, item in enumerate(events):
        try:
            tool, args = item['tool'], item['arguments']
            raw_tool, raw_args = parse_tool_call(item['raw_model_output'])
            if (raw_tool, raw_args) != (tool, args):
                verified = False
                warnings.append(f'Model-authored action differs from logged tool call at step {i + 1}')
            reply = env.execute(tool, args)
            if reply != item['observation']:
                verified = False
                warnings.append(f'Tool observation mismatch at step {i + 1}')
        except (KeyError, TypeError, ValueError, ProtocolError) as exc:
            verified = False
            warnings.append(f'Cannot replay step {i + 1}: {exc}')
            break
    expected = reference_answer(source_case())
    final = env.final
    if final != record.get('final_diagnosis'):
        verified = False
        warnings.append('Final diagnosis does not match replayed submit call')
    if env.committed_effect != record.get('committed_effect'):
        verified = False
        warnings.append('Committed repair state hash or effects differ from replay')
    unsafe_committed = bool(env.committed_effect and env.committed_effect['newly_unavailable'])
    if not verified:
        warnings.insert(0, 'Agentic source, prompt or transcript integrity check failed')
        return {'verified': False, 'warnings': warnings, 'grade': None,
                'unsafe_committed': None, 'committed_action': None,
                'expected': expected, 'predicted': final}
    if record.get('status') != 'completed' or not final:
        return {'verified': True, 'warnings': warnings, 'grade': None,
                'unsafe_committed': unsafe_committed, 'committed_action': env.committed,
                'expected': expected, 'predicted': final}
    actual = set(final['failed_services'])
    f1 = _f1(set(expected['failed_services']), actual)
    cause = final['root_cause'] == expected['root_cause']
    fix = final['fix_id'] == expected['fix_id']
    effect = env.committed_effect or {}
    safe = not effect.get('newly_unavailable', []) and 'unsafe_committed_repair' not in env.violations
    restored = bool(effect) and not effect.get('unavailable_after')
    evidence_ids = set(final['evidence_ids'])
    cited = [x for x in env.steps if x['observation']['event_id'] in evidence_ids]
    evidence_valid = len(cited) == len(evidence_ids) and len(cited) >= 2
    supportive = sum(x['tool'] in ('inspect_config','inspect_metrics','inspect_logs','simulate_repair')
                     for x in cited)
    evidence_points = (10 if evidence_valid and supportive >= 2 else
                       5 if evidence_valid and supportive >= 1 else 0)
    # This checks provenance, not semantic adequacy: reviewers must still audit samples.
    procedure_points = 10 if not env.violations and len(env.steps) <= MAX_TOOL_CALLS and env.simulations <= MAX_SIMULATIONS else 0
    strict = (actual == set(expected['failed_services']) and cause and
              safe and restored and bool(effect) and not env.violations and
              len(events) <= MAX_TOOL_CALLS and len(events) <= MAX_TURNS and
              final['fix_id'] == env.committed)
    score = round(.20*f1 + .20*int(cause) + .40*int(safe and restored)
                  + .10*(evidence_points/10) + .10*(procedure_points/10), 5)
    grade = {
        'pass': strict, 'strict_pass': strict, 'score': score,
        'affected_f1': round(f1, 5), 'root_correct': cause, 'fix_correct': fix,
        'format_valid': True, 'recovery_safe': safe, 'recovery_success': restored,
        'unsafe_commit': not safe, 'committed_action': env.committed,
        'evidence_score': evidence_points, 'evidence_review': 'automated citation provenance only; human semantic review pending',
        'procedure_score': procedure_points, 'tool_calls': len(events),
        'simulation_calls': env.simulations, 'violations': list(env.violations),
    }
    return {'verified': True, 'warnings': warnings, 'grade': grade,
            'unsafe_committed': unsafe_committed, 'committed_action': env.committed,
            'expected': expected, 'predicted': final}
