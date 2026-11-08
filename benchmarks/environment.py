"""Single task-parameterized simulator. No cloud access or manual model loop.

Every tool executes only against a copy of a source-grounded modeled fixture;
all state transitions use the independently tested declarative oracle.
"""
from __future__ import annotations
from copy import deepcopy
from typing import Any
from oracle import initial_failures, patch_facts, simulate
from benchmarks.spec import TaskSpec, digest, service_codes, synthetic_task

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
        self.codes = service_codes(spec.id)
        self.reverse_codes = {code: name for name, code in self.codes.items()}
        self.v5 = synthetic_task(spec.id)
        self.v6 = spec.id.endswith(('V6N', 'V6CF'))

    def encode(self, services):
        return sorted(self.codes.get(n, n) for n in services)

    def decode(self, services):
        return [self.reverse_codes.get(n, n) for n in services]

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
                                     or args['service'] not in (self.reverse_codes if self.v5 else self.nodes)):
            raise ProtocolError('Unknown service ID')
        if tool in ACTION_TOOLS and (not isinstance(args['action_id'], str)
                                    or args['action_id'] not in self.actions):
            raise ProtocolError('Unknown repair ID')
        if tool == 'prepare_repair':
            if self.repair_brief is not None:
                raise ProtocolError('Repair handoff already submitted; use repair-phase tools')
            if not any(x['tool'] == 'list_repairs' for x in self.steps):
                raise ProtocolError('Inspect available repairs before preparing a repair handoff')
            services, citations = args['failed_services'], args['evidence_ids']
            valid_ids = {x['observation']['event_id'] for x in self.steps}
            if (not isinstance(services, list) or not services
                or not all(isinstance(v, str) and v in (self.reverse_codes if self.v5 else self.nodes) for v in services)
                or len(services) != len(set(services))
                or not isinstance(citations, list) or len(citations) < 2
                or not all(isinstance(x, str) and x in valid_ids for x in citations)
                or len(citations) != len(set(citations))
                or not isinstance(args['hypothesized_root_cause_id'], str)
                or args['hypothesized_root_cause_id'] not in {h for h, _ in self.spec.hypotheses}
                or not isinstance(args['repair_instructions'], str)
                or not 60 <= len(args['repair_instructions'].strip()) <= 2200):
                raise ProtocolError('Invalid repair handoff: cite observed events and provide an evidence-backed plan (60-2200 characters)')

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
        if self.closed or len(self.steps) >= self.spec.max_tools:
            raise ProtocolError('Episode is closed or tool budget exceeded')
        self._arguments(tool, args)
        event_id = f'EV{len(self.steps) + 1:03d}'
        before_down, _ = simulate(self.case, self.facts)
        direct, _ = initial_failures(self.case['id'], self.facts)
        if tool == 'scan_service_health':
            # V6 exposes only externally observable entrypoint probes; the
            # internal inventory must be resolved through individual inspections.
            visible = ([n for n in sorted(self.nodes) if not any(
                n in (m.get('needs_all', []) + m.get('needs_any', []) +
                      (m.get('needs_at_least') or {}).get('of', []))
                for m in self.nodes.values())] if self.v6 else sorted(self.nodes))
            observation = {
                'snapshot': 'initial', 'kind': 'synthetic availability probes',
                'statuses': {self.codes.get(name, name): ('unavailable' if name in self.original_down else 'healthy')
                             for name in visible},
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
                           **({'service_inventory': [{'service_code': code, 'role': name} for name, code in sorted(self.codes.items())]} if self.v5 else {}),
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
            observation = {'candidate_repairs': [
                {'id': a['id'], 'cost': a['cost'],
                 'meaning': (a.get('operational_description', 'Operator-proposed change; verify conditions and counterfactual effects') if self.v6 else 'Proposed operational change; simulate to verify service impact' if self.v5 else f"Candidate with {len(a['changes'])} configuration edit(s)"),
                 **({} if self.v5 else {'changes': deepcopy(a['changes'])})}
                for a in self.case['actions']]}
        elif tool in SERVICE_TOOLS:
            name = self.reverse_codes.get(args['service'], args['service'])
            node = self.nodes[name]
            if tool == 'inspect_config':
                observation = {'service': args['service'], **self._local_details(name)}
                if self.v6:
                    # Publish factual preconditions only through local investigation,
                    # not through success labels or reference-optimal hints.
                    prereqs = []
                    for action in self.case['actions']:
                        if action.get('precondition_service') == name and action.get('precondition'):
                            req = action['precondition']
                            value = self.facts
                            for part in req['path']: value = value[part]
                            prereqs.append({'action_id': action['id'], 'path': req['path'],
                                            'operator': 'eq', 'expected': req['equals'], 'observed': value})
                    if prereqs: observation['candidate_precondition_checks'] = prereqs
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
                observation = {'service': args['service'], 'timestamp': self.spec.time,
                               'health_probe': 'unavailable' if name in before_down else 'healthy',
                               'synthetic_request_errors_per_minute': 60 if name in before_down else 0,
                               **({'is_direct_local_fault': name in direct} if self.spec.id.endswith('V3') else {})}
            else:
                # V5/V6: do not announce direct versus cascading failures in logs.
                # Only inspection of local rules and dependencies can distinguish them.
                if self.spec.id.endswith(('V5', 'V6N', 'V6CF')):
                    message = ('service unavailable; investigate configuration and dependencies'
                               if name in before_down else 'health probe passing')
                else:
                    message = (('local check violation; inspect the relevant configuration values'
                                if self.spec.id.endswith('V3') else 'synthetic service health probe failed')
                               if name in direct else 'upstream request unavailable; trace dependencies'
                               if name in before_down else 'health probe passing')
                observation = {'service': args['service'], 'timestamp': self.spec.time,
                               'lines': [f'{self.spec.time} {args["service"]} {message}']}
        elif tool == 'simulate_repair':
            if self.repair_brief is None:
                raise ProtocolError('Call prepare_repair with an evidence-backed plan before simulation')
            if self.simulations >= self.spec.max_simulations:
                raise ProtocolError('Simulation-call budget exceeded')
            self.simulations += 1
            action = self.actions[args['action_id']]
            changed = patch_facts(self.facts, action)
            after_down, _ = simulate(self.case, changed)
            observation = {'action_id': action['id'], 'cost': action['cost'],
                           'unavailable_after_count': len(after_down),
                           'restored_count': len(before_down - after_down),
                           'newly_unavailable_count': len(after_down - before_down),
                           'newly_unavailable_services': self.encode(after_down - before_down),
                           'unavailable_after_services': self.encode(after_down),
                           'simulated_only': True,
                           'state_unchanged': True,
                           'simulations_remaining': self.spec.max_simulations - self.simulations}
        elif tool == 'apply_repair':
            if self.repair_brief is None:
                raise ProtocolError('Call prepare_repair before committing a sandbox repair')
            if self.committed is not None:
                self.violations.append('attempted_second_commit')
                raise ProtocolError('Only one committed repair is allowed')
            action = self.actions[args['action_id']]
            self.facts = patch_facts(self.facts, action)
            after_down, _ = simulate(self.case, self.facts)
            self.committed = action['id']
            self.committed_effect = {'action_id': action['id'], 'unavailable_after': self.encode(after_down),
                                     'newly_unavailable': self.encode(after_down - before_down),
                                     'restored': self.encode(before_down - after_down),
                                     'facts_sha256': digest(self.facts)}
            observation = {'action_id': action['id'], 'committed_in_sandbox': True,
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
                or len(set(services)) != len(services) or any(s not in (self.reverse_codes if self.v5 else self.nodes) for s in services)
                or not isinstance(args['root_cause_id'], str)
                or args['root_cause_id'] not in {label for label, _ in self.spec.hypotheses}
                or not isinstance(args['root_cause_explanation'], str)
                or not 20 <= len(args['root_cause_explanation'].strip()) <= 1200
                or not isinstance(args['fix_id'], str)
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

