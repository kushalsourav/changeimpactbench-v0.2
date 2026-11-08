"""Single task-parameterized simulator. No cloud access or manual model loop.

Every tool executes only against a copy of a source-grounded modeled fixture;
all state transitions use the independently tested declarative oracle.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timedelta
from oracle import initial_failures, patch_facts, simulate
from benchmarks.spec import TaskSpec, digest, service_codes, synthetic_task, public_action_ids

class ProtocolError(ValueError):
    pass

SERVICE_TOOLS = {'inspect_logs', 'inspect_metrics', 'inspect_config', 'inspect_dependencies'}
ACTION_TOOLS = {'simulate_repair', 'apply_repair'}

class AgentEnvironment:
    def __init__(self, spec: TaskSpec, case: dict):
        self.spec = spec
        self.case = deepcopy(case)
        self.original_facts = deepcopy(self.case['facts'])
        self.facts = deepcopy(self.original_facts)
        self.original_down, _ = simulate(self.case)
        self.steps: list[dict] = []
        self.simulations = 0
        self.committed: str | None = None
        self.committed_effect: dict | None = None
        self.final: dict | None = None
        self.repair_brief: dict | None = None
        self.closed = False
        self.violations: list[str] = []
        self.nodes = {n['id']: n for n in self.facts['topology']}
        self.actions = {a['id']: a for a in self.case['actions']}
        self.public_actions = public_action_ids(spec.id)
        self.private_actions = {public: private for private, public in self.public_actions.items()}
        self.codes = service_codes(spec.id)
        self.reverse_codes = {code: name for name, code in self.codes.items()}
        self.synthetic_codes = True
        self.v6 = spec.id.endswith('V6CF')
        self.observability = deepcopy(self.case.get('observability') or {})

    def encode(self, services):
        return sorted(self.codes.get(n, n) for n in services)

    def decode(self, services):
        return [self.reverse_codes.get(n, n) for n in services]

    def observed_at(self, age_seconds: int) -> str:
        """Return the actual sample time, preserving deterministic fixture time."""
        snapshot = self.observability.get('snapshot_time', self.spec.time)
        try:
            value = datetime.fromisoformat(snapshot.replace('Z', '+00:00'))
            return (value - timedelta(seconds=age_seconds)).isoformat().replace('+00:00', 'Z')
        except (TypeError, ValueError):
            return snapshot

    def encode_node(self, node):
        output = deepcopy(node)
        for key in ('id', 'service'):
            if key in output: output[key] = self.codes.get(output[key], output[key])
        for key in ('needs_all', 'needs_any'):
            if key in output: output[key] = self.encode(output[key])
        if output.get('needs_at_least'):
            output['needs_at_least']['of'] = self.encode(output['needs_at_least']['of'])
        return output

    def _arguments(self, tool: str, args: dict) -> None:
        expected = (set() if tool in ('read_alert', 'list_repairs', 'scan_service_health') else
                    {'service'} if tool in SERVICE_TOOLS else
                    {'action_id'} if tool in ACTION_TOOLS else
                    {'failed_services', 'hypothesized_root_cause_id', 'repair_instructions', 'evidence_ids'} if tool == 'prepare_repair' else
                    {'failed_services', 'root_cause_id', 'root_cause_explanation', 'fix_id', 'evidence_ids', 'rationale'})
        if set(args) != expected:
            raise ProtocolError(f'{tool} expects exactly {sorted(expected)}')
        if tool in SERVICE_TOOLS and (not isinstance(args['service'], str)
                                     or args['service'] not in (self.reverse_codes if self.synthetic_codes else self.nodes)):
            raise ProtocolError('Unknown service ID')
        if tool in ACTION_TOOLS and (not isinstance(args['action_id'], str)
                                    or args['action_id'] not in self.private_actions):
            raise ProtocolError('Unknown repair ID')
        if tool == 'prepare_repair':
            if self.repair_brief is not None:
                raise ProtocolError('Repair handoff already submitted; use repair-phase tools')
            if not any(x['tool'] == 'list_repairs' for x in self.steps):
                raise ProtocolError('Inspect available repairs before preparing a repair handoff')
            services, citations = args['failed_services'], args['evidence_ids']
            valid_ids = {x['observation']['event_id'] for x in self.steps}
            if (not isinstance(services, list) or not services
                or not all(isinstance(v, str) and v in (self.reverse_codes if self.synthetic_codes else self.nodes) for v in services)
                or len(services) != len(set(services))
                or not isinstance(citations, list) or len(citations) < 2
                or not all(isinstance(x, str) and x in valid_ids for x in citations)
                or len(citations) != len(set(citations))
                or not isinstance(args['hypothesized_root_cause_id'], str)
                or args['hypothesized_root_cause_id'] not in {h for h, _ in self.spec.hypotheses}
                or not isinstance(args['repair_instructions'], str)
                or not 60 <= len(args['repair_instructions'].strip()) <= 2200):
                raise ProtocolError('Invalid repair handoff: cite observed events and provide an evidence-backed plan (60-2200 characters)')

    def execute(self, tool: str, args: dict) -> dict:
        """Execute one validated sandbox tool and return exactly what the model sees."""
        if self.closed or len(self.steps) >= self.spec.max_tools:
            raise ProtocolError('Episode is closed or tool budget exceeded')
        self._arguments(tool, args)
        event_id = f'EV{len(self.steps) + 1:03d}'
        before_down, _ = simulate(self.case, self.facts)
        direct, _ = initial_failures(self.case['id'], self.facts)
        if tool == 'scan_service_health':
            # Source-faithful fixtures choose a bounded set of model-facing
            # probes. Fall back to graph entrypoints for older fixtures.
            declared = self.observability.get('external_probes') or []
            visible = (declared if declared else [n for n in sorted(self.nodes) if not any(
                n in (m.get('needs_all', []) + m.get('needs_any', []) +
                      (m.get('needs_at_least') or {}).get('of', []))
                for m in self.nodes.values())]) if self.v6 else sorted(self.nodes)
            telemetry = self.observability.get('services') or {}
            def reported(name):
                row = telemetry.get(name) or {}
                return row.get('reported_health') or ('unavailable' if name in self.original_down else 'healthy')
            observation = {
                'snapshot': 'initial', 'kind': 'synthetic availability probes',
                'observed_at': self.observability.get('snapshot_time', self.spec.time),
                'statuses': {self.codes.get(name, name): reported(name) for name in visible},
                'service_count': len(self.nodes),
                **({'probe_scope': 'external endpoint probes only; inspect_metrics on each inventory service to determine complete internal impact',
                     'observed_count': len(visible)} if self.v6 else {}),
                'root_cause_withheld': True,
            }
        elif tool == 'read_alert':
            observation = {'time': self.spec.time,
                           'alert': self.spec.alert +
                           ' Identify every initially failed service; select the lowest-cost complete safe repair.',
                           'observations': list(self.spec.observations),
                           'hypotheses': [{'id': id_, 'description': description}
                                          for id_, description in self.spec.hypotheses],
                           'service_inventory': sorted(self.codes.values()),
                'inventory_scope': 'Opaque component identifiers; infer relationships and failures using available inspection tools.',
                           'scope': 'Synthetic research fixture; reference result withheld'}
        elif tool == 'prepare_repair':
            self.repair_brief = deepcopy(args)
            observation = {
                'phase': 'repair', 'handoff_accepted': True,
                'author': 'investigating model (NOT oracle)',
                'evidence_ids': deepcopy(args['evidence_ids']),
                'available_simulations': self.spec.max_simulations,
                'message': 'Repair-phase skill now active. The plan is a hypothesis. Simulate and verify independently before committing.',
            }
        elif tool == 'list_repairs':
            observation = {'candidate_repairs': sorted([
                {'id': self.public_actions[a['id']], 'cost': a['cost'],
                 'estimated_minutes': a.get('estimated_minutes'),
                 'risk': a.get('risk', 'unknown'),
                 'operational_description': a.get('operational_description', 'Bounded incident response action.'),
                 'meaning': 'Candidate operational response; outcome is not asserted.'}
                for a in self.case['actions']], key=lambda a: a['id'])}
        elif tool in SERVICE_TOOLS:
            name = self.reverse_codes.get(args['service'], args['service'])
            node = self.nodes[name]
            source = deepcopy((self.observability.get('services') or {}).get(name) or {})
            age = int(source.get('measurement_age_seconds') or 0)
            observed_at = self.observed_at(age)
            freshness = 'stale' if age >= 60 else 'fresh'
            if tool == 'inspect_config':
                # Do not expose the executable oracle predicate. Models receive
                # the kind of raw snapshot an operator could inspect and must
                # infer whether it explains the observed symptoms.
                observation = {
                    'service': args['service'], 'observed_at': observed_at,
                    'measurement_age_seconds': age, 'freshness': freshness,
                    'configuration_snapshot': deepcopy(source.get('configuration_snapshot') or {}),
                    'snapshot_scope': 'raw modeled configuration; no oracle failure predicate or repair answer',
                }
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
                observation = {'service': args['service'], 'upstream': self.encode_node(upstream),
                               'direct_consumers': self.encode(consumers),
                               'consumer_dependency_rules': {self.codes.get(k,k): self.encode_node(v) for k,v in consumer_rules.items()}}
            elif tool == 'inspect_metrics':
                reported = source.get('reported_health') or ('unavailable' if name in before_down else 'healthy')
                signals = deepcopy(source.get('signals') or {})
                if not signals:
                    signals = {'request_error_rate_pct': 100.0 if name in before_down else 0.0}
                observation = {'service': args['service'], 'observed_at': observed_at,
                               'measurement_age_seconds': age, 'freshness': freshness,
                               'health_probe': reported, 'signals': signals,
                               'interpretation_note': 'A stale or partial observation may not equal current ground truth; corroborate with dependencies and other signals.'}
            else:
                lines = deepcopy(source.get('logs') or [])
                if not lines:
                    lines = ['request path unavailable; correlate local signals and upstream dependencies'
                             if name in before_down else 'routine health event; no current serving error recorded']
                observation = {'service': args['service'], 'observed_at': observed_at,
                               'measurement_age_seconds': age, 'freshness': freshness,
                               'lines': [f'{observed_at} {args["service"]} {line}' for line in lines]}
        elif tool == 'simulate_repair':
            if self.repair_brief is None:
                raise ProtocolError('Call prepare_repair with an evidence-backed plan before simulation')
            if self.simulations >= self.spec.max_simulations:
                raise ProtocolError('Simulation-call budget exceeded')
            self.simulations += 1
            action = self.actions[self.private_actions[args['action_id']]]
            changed = patch_facts(self.facts, action)
            after_down, _ = simulate(self.case, changed)
            observation = {'action_id': args['action_id'], 'cost': action['cost'],
                           # Opaque outcomes: only aggregate counts, not service identities,
                           # their roles, cause labels, or an oracle optimality verdict.
                           'unavailable_after_count': len(after_down),
                           'restored_count': len(before_down - after_down),
                           'newly_unavailable_count': len(after_down - before_down),
                           'simulated_only': True,
                           'state_unchanged': True,
                           'simulations_remaining': self.spec.max_simulations - self.simulations}
        elif tool == 'apply_repair':
            if self.repair_brief is None:
                raise ProtocolError('Call prepare_repair before committing a sandbox repair')
            if self.committed is not None:
                self.violations.append('attempted_second_commit')
                raise ProtocolError('Only one committed repair is allowed')
            action = self.actions[self.private_actions[args['action_id']]]
            self.facts = patch_facts(self.facts, action)
            after_down, _ = simulate(self.case, self.facts)
            self.committed = args['action_id']
            self.committed_effect = {'action_id': args['action_id'], 'unavailable_after': self.encode(after_down),
                                     'newly_unavailable': self.encode(after_down - before_down),
                                     'restored': self.encode(before_down - after_down),
                                     'facts_sha256': digest(self.facts)}
            observation = {'action_id': args['action_id'], 'committed_in_sandbox': True,
                           'unavailable_after_count': len(after_down),
                           'newly_unavailable_count': len(after_down - before_down),
                           'restored_count': len(before_down - after_down),
                           'synthetic_only': True}
            if after_down - before_down:
                self.violations.append('unsafe_committed_repair')
        else:
            if self.repair_brief is None:
                raise ProtocolError('Missing investigator-to-repair handoff')
            if self.committed is None:
                raise ProtocolError('Commit a sandbox repair before submitting a diagnosis')
            services = args['failed_services']
            ids = args['evidence_ids']
            if (not isinstance(services, list) or not all(isinstance(x, str) for x in services)
                or len(set(services)) != len(services) or any(s not in (self.reverse_codes if self.synthetic_codes else self.nodes) for s in services)
                or not isinstance(args['root_cause_id'], str)
                or args['root_cause_id'] not in {label for label, _ in self.spec.hypotheses}
                or not isinstance(args['root_cause_explanation'], str)
                or not 20 <= len(args['root_cause_explanation'].strip()) <= 1200
                or not isinstance(args['fix_id'], str) or args['fix_id'] not in self.private_actions
                or not isinstance(ids, list) or not all(isinstance(x, str) for x in ids)
                or len(set(ids)) != len(ids) or not isinstance(args['rationale'], str)
                or not 30 <= len(args['rationale'].strip()) <= 2000):
                raise ProtocolError('Invalid final diagnosis fields or unknown service')
            self.final = deepcopy(args)
            self.closed = True
            observation = {'received': True, 'final_status': 'submitted_for_independent_grading'}
        reply = {'event_id': event_id, 'tool': tool, 'result': observation}
        self.steps.append({'tool': tool, 'arguments': deepcopy(args), 'observation': deepcopy(reply)})
        return reply
