"""V6CF-only reproducibility tests; scripted model acts as a reference solution, NOT evidence."""
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
import json
import unittest
from unittest.mock import patch

from agent_graph import ACTIVE_TASK_IDS, TASK_IDS, GraphEnvironment, agent_prompt, implementation_hashes
from benchmarks.spec import reference_path, source_case, service_codes, get_spec, reference_trajectory, public_action_ids
from benchmarks.grader import replay_record
from benchmarks.environment import AgentEnvironment
from dashboard_data import audit_record, replay_saved_record
from oracle import reference_answer, simulate, patch_facts
from run_graph_agent import run_episode
from benchmarks.input_budget import (InputTokenBudget, InputTokenBudgetExceeded,
    InputTokenUsageUnavailable, reported_input_tokens)

TASKS = [f'RW{i:02}V6CF' for i in range(1, 7)]


class ScriptedReferenceGraph:
    """Deterministic oracle tool emitter; NEVER scored as an actual AI provider."""
    def __init__(self, env, *, wrong_cause=False, unsafe=False, empty_evidence=False,
                 final_evidence_tools=None):
        self.env = env
        self.wrong_cause = wrong_cause
        self.unsafe = unsafe
        self.empty_evidence = empty_evidence
        self.final_evidence_tools = final_evidence_tools

    def stream(self, _input, config, stream_mode):
        for idx, (tool, arguments) in enumerate(reference_trajectory(self.env.task_id), 1):
            args = deepcopy(arguments)
            if self.wrong_cause and tool == 'submit_diagnosis':
                args['root_cause_id'] = 'H01' if args['root_cause_id'] != 'H01' else 'H02'
            if self.unsafe and tool == 'apply_repair':
                args['action_id'] = public_action_ids(self.env.task_id)['A90']
            if self.empty_evidence and tool == 'submit_diagnosis':
                args['evidence_ids'] = ['EV001', 'EV002']
            if self.final_evidence_tools and tool == 'submit_diagnosis':
                selected = []
                for wanted_tool in self.final_evidence_tools:
                    event = next(
                        step for step in self.env.steps
                        if step['tool'] == wanted_tool
                        and step['observation']['event_id'] not in selected
                    )
                    selected.append(event['observation']['event_id'])
                args['evidence_ids'] = selected
            ident = f'scripted-{idx}'
            yield {'model': {'messages': [SimpleNamespace(
                type='ai', content='', tool_calls=[{'name': tool, 'args': args, 'id': ident}],
                usage_metadata={}, response_metadata={}, additional_kwargs={}, id=ident,
            )]}}
            observation = self.env.execute(tool, args, ident)
            yield {'tools': {'messages': [SimpleNamespace(type='tool', content=observation)]}}


def run_scripted(task_id: str, **changes) -> dict:
    with redirect_stdout(StringIO()):
        return run_episode(task_id, 'scripted/reference:free', 1, 'not-a-real-key',
                           2000, 'low', 0, 3,
                           graph_factory=lambda env, *_: ScriptedReferenceGraph(env, **changes))


class FakeBudgetedGraph:
    """One real-shaped AI message; emulate next-request gate without a provider."""
    def __init__(self, env):
        self.env = env

    def stream(self, _input, config, stream_mode):
        self.env.graph_request_limit_active = True
        self.env.input_token_budget.before_request()
        self.env.model_requests_started = 1
        self.env.model_phases[1] = self.env.phase
        fake_message = SimpleNamespace(
            type='ai', content='', tool_calls=[{'name': 'read_alert', 'args': {}, 'id': 'budget-1'}],
            usage_metadata={'input_tokens': 4500, 'output_tokens': 10},
            response_metadata={}, additional_kwargs={}, id='fake-budget-response',
        )
        self.env.input_token_budget.after_response(SimpleNamespace(result=[fake_message]))
        yield {'model': {'messages': [fake_message]}}
        self.env.provider_turn = 1
        observed = self.env.execute('read_alert', {}, 'budget-1')
        yield {'tools': {'messages': [SimpleNamespace(type='tool', content=observed)]}}
        self.env.input_token_budget.before_request()
        raise AssertionError('Next provider request must not be dispatched')


class V6CounterfactualTests(unittest.TestCase):
    def test_source_faithful_revision_rejects_old_runner_hash(self):
        record = run_scripted('RW01V6CF')
        legacy = deepcopy(record)
        legacy['source_hashes']['benchmarks/runner.py'] = (
            '7007f8a01282ed54751cf12090260c471a2858ffe88a1242a4aa7bd9f1e2baa9'
        )
        # The new telemetry and repair contract is semantic, so earlier saved
        # episodes must be rerun rather than migrated into the new benchmark.
        self.assertFalse(replay_saved_record(legacy)['verified'])
        legacy['source_hashes']['benchmarks/runner.py'] = '0' * 64
        self.assertFalse(replay_saved_record(legacy)['verified'])

    def test_cumulative_provider_input_budget_stops_before_next_request(self):
        budget = InputTokenBudget(4096)
        response = SimpleNamespace(result=[SimpleNamespace(usage_metadata={'input_tokens': 4500})])
        self.assertEqual(reported_input_tokens(response), 4500)
        budget.before_request()
        budget.after_response(response)
        self.assertEqual(budget.used, 4500)
        with self.assertRaises(InputTokenBudgetExceeded):
            budget.before_request()

        incomplete = run_episode('RW01V6CF', 'scripted/reference:free', 1,
                                 'no-provider', 2000, 'low', 0, 3,
                                 graph_factory=lambda env, *_: FakeBudgetedGraph(env),
                                 max_input_tokens=4096)
        self.assertEqual(incomplete['status'], 'input_budget_exhausted')
        self.assertEqual(incomplete['termination_reason'], 'input_token_budget')
        self.assertEqual(incomplete['provider_requests'], 1)
        self.assertEqual(incomplete['usage']['prompt_tokens'], 4500)
        self.assertEqual(incomplete['max_input_tokens_requested'], 4096)
        self.assertTrue(incomplete['replay_verified'])
        self.assertNotIn('grade', incomplete)

    def test_ten_million_input_token_ceiling_and_anthropic_runner_import(self):
        import subprocess
        import sys
        from benchmarks.input_budget import MAX_MAX_INPUT_TOKENS

        self.assertEqual(MAX_MAX_INPUT_TOKENS, 10_000_000)
        self.assertEqual(InputTokenBudget(10_000_000).limit, 10_000_000)
        with self.assertRaises(ValueError):
            InputTokenBudget(10_000_001)
        # Regression: an undefined _stop_signal import previously prevented
        # all direct Anthropic runs, even before the API call.
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parents[1] / 'tools/run_anthropic.py'), '--help'],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--max-input-tokens', result.stdout)

    def test_mixed_runner_forwards_20k_output_ceiling_to_all_providers(self):
        from tools.run_mixed_providers import commands
        models = ['nvidia/mock:free', 'anthropic/claude-test', 'google-ai-studio/gemini-test']
        paths = ['results/openrouter.jsonl', 'results/anthropic.jsonl', 'results/gemini.jsonl']
        lines = list(commands(models, 'RW01V6CF', 1, 4, 0, 20_000, 'low', paths, 10_000_000))
        self.assertEqual(len(lines), 3)
        for line in lines:
            self.assertEqual(line[line.index('--max-tokens') + 1], '20000')
            self.assertEqual(line[line.index('--max-input-tokens') + 1], '10000000')

    def test_missing_provider_input_usage_prevents_further_calls(self):
        budget = InputTokenBudget(30000)
        budget.before_request()
        budget.after_response(SimpleNamespace(result=[SimpleNamespace(usage_metadata={})]))
        self.assertTrue(budget.usage_missing)
        with self.assertRaises(InputTokenUsageUnavailable):
            budget.before_request()

    def test_input_budget_reaches_every_provider_child(self):
        from tools.run_mixed_providers import commands
        ids = ['nvidia/mock:free', 'anthropic/claude-test', 'google-ai-studio/gemini-test']
        output = ['results/one.jsonl', 'results/two.jsonl', 'results/three.jsonl']
        command_lines = list(commands(ids, 'RW01V6CF', 1, 4, 0, 8000, 'low', output, 75000))
        self.assertEqual(len(command_lines), 3)
        for line in command_lines:
            i = line.index('--max-input-tokens')
            self.assertEqual(line[i+1], '75000')

    def test_only_six_counterfactual_task_ids(self):
        self.assertEqual(TASK_IDS, ACTIVE_TASK_IDS)
        self.assertEqual(set(TASKS), set(ACTIVE_TASK_IDS))
        for removed in ('RW01V4', 'RW01V5', 'RW01V6N', 'RW01V3'):
            with self.assertRaises(ValueError):
                get_spec(removed)

    def test_original_named_reference_files_and_oracle_agree(self):
        for task_id in TASKS:
            with self.subTest(task=task_id):
                case = source_case(task_id)
                stored = json.loads(reference_path(task_id).read_text(encoding='utf-8'))
                expected = reference_answer(case)
                self.assertEqual(stored, expected)
                self.assertEqual(set(expected['failed_services']), simulate(case)[0])
                outcomes = sorted((a['cost'], a['id']) for a in case['actions']
                                  if not simulate(case, patch_facts(case['facts'], a))[0])
                self.assertGreater(len(outcomes), 1)
                self.assertEqual(outcomes[0][1], expected['fix_id'])
                a90 = next(x for x in case['actions'] if x['id'] == 'A90')
                unsafe, _ = simulate(case, patch_facts(case['facts'], a90))
                self.assertTrue(unsafe - simulate(case)[0])
                self.assertEqual(set(service_codes(task_id)),
                                 {n['id'] for n in case['facts']['topology']})
                self.assertGreaterEqual(len(case['facts']['topology']), 18)
                self.assertFalse(any('validated-shard' in n['id'] or 'quorum-gateway' in n['id']
                                     for n in case['facts']['topology']))
                self.assertEqual(reference_path(task_id).parent.name, 'v6-counterfactual')

    def test_source_specific_topology_and_partial_timestamped_telemetry(self):
        topology_signatures = set()
        signal_names = set()
        for task_id in TASKS:
            case = source_case(task_id)
            nodes = case['facts']['topology']
            topology_signatures.add((
                len(nodes),
                sum(len(node.get('needs_all', [])) for node in nodes),
                sum(len(node.get('needs_any', [])) for node in nodes),
                sum(bool(node.get('needs_at_least')) for node in nodes),
            ))
            telemetry = case['observability']
            rows = telemetry['services']
            self.assertEqual(set(rows), {node['id'] for node in nodes})
            self.assertLess(len(telemetry['external_probes']), len(nodes))
            self.assertTrue(any(not row.get('signals') for row in rows.values()))
            stale_name = next(name for name, row in rows.items()
                              if int(row.get('measurement_age_seconds', 0)) >= 60)
            signal_names.update(key for row in rows.values() for key in row.get('signals', {}))
            env = AgentEnvironment(get_spec(task_id), case)
            stale = env.execute('inspect_metrics', {
                'service': service_codes(task_id)[stale_name],
            })['result']
            self.assertEqual(stale['freshness'], 'stale')
            self.assertNotEqual(stale['observed_at'], telemetry['snapshot_time'])
        self.assertEqual(len(topology_signatures), len(TASKS))
        for required in ('error', 'latency', 'cpu', 'replication', 'queue', 'location'):
            self.assertTrue(any(required in name for name in signal_names), required)

    def test_tools_observable_and_no_source_name_leak(self):
        for task_id in TASKS:
            with self.subTest(task=task_id):
                prompt = agent_prompt(task_id)
                parsed = json.loads(prompt)
                self.assertNotIn('incident_name', parsed)
                self.assertNotIn('source_url', parsed)
                self.assertNotIn('GitHub', prompt)
                self.assertNotIn('Cloudflare', prompt)
                self.assertIn('external entrypoint probes only', prompt)
                env = AgentEnvironment(get_spec(task_id), source_case(task_id))
                alert = env.execute('read_alert', {})['result']
                self.assertEqual(set(alert['service_inventory']), set(service_codes(task_id).values()))
                self.assertNotIn('role', json.dumps(alert['service_inventory']))
                self.assertNotIn('mysql', json.dumps(alert['service_inventory']))
                scan = env.execute('scan_service_health', {})['result']
                self.assertLess(scan['observed_count'], scan['service_count'])
                # No copy-paste of the full failure set in a single scan.
                self.assertLess(len(scan['statuses']), scan['service_count'])
                repairs = env.execute('list_repairs', {})['result']['candidate_repairs']
                codes_map = public_action_ids(task_id)
                self.assertEqual({a['id'] for a in repairs}, set(codes_map.values()))
                self.assertTrue(all('edit_targets' not in a for a in repairs))
                self.assertTrue(all(a.get('operational_description') and a.get('estimated_minutes') is not None
                                    and a.get('risk') for a in repairs))
                self.assertTrue(all('safe' not in a['meaning'].lower() and
                                    'optimal' not in a['meaning'].lower() for a in repairs))
                simulation = env.execute('prepare_repair', {
                    'failed_services': list(sorted(service_codes(task_id).values()))[:1],
                    'hypothesized_root_cause_id': get_spec(task_id).hypotheses[0][0],
                    'repair_instructions': 'Investigate local rules and dependency edges before committing a safe complete repair; evaluate modeled candidates and choose based on the observed counterfactual outcomes.',
                    'evidence_ids': [f'EV{i:03d}' for i in (1, 2)],
                })['result']
                self.assertTrue(simulation['handoff_accepted'])
                simulated = env.execute('simulate_repair', {'action_id': codes_map['A90']})['result']
                self.assertNotIn('unavailable_after_services', simulated)
                self.assertNotIn('newly_unavailable_services', simulated)
                self.assertGreater(simulated['newly_unavailable_count'], 0)
                case = source_case(task_id)
                direct, _ = __import__('oracle', fromlist=['initial_failures']).initial_failures(case['id'], case['facts'])
                for name in direct:
                    config = env.execute('inspect_config', {'service':service_codes(task_id)[name]})['result']
                    self.assertNotIn('rule', config)
                    self.assertNotIn('referenced_values', config)
                    self.assertTrue(config['configuration_snapshot'])

    def test_public_repair_ids_hide_cross_case_optimality_shortcut(self):
        private_optima = []
        public_optima = []
        for task_id in TASKS:
            case = source_case(task_id)
            internal = reference_answer(case)['fix_id']
            private_optima.append(internal)
            public = public_action_ids(task_id)
            public_optima.append(public[internal])
            self.assertEqual(len(set(public)), len(public))
            self.assertEqual(set(public), {a['id'] for a in case['actions']})
            self.assertEqual(set(public.values()), {f'R{i:02}' for i in range(1, len(public) + 1)})
        # Source-specific response sets must not share one hidden optimum ID.
        self.assertGreaterEqual(len(set(private_optima)), 5)
        self.assertGreaterEqual(len(set(public_optima)), 4)

    def test_hypotheses_are_competitive_and_alerts_not_postmortem_titles(self):
        for task_id in TASKS:
            hypotheses = get_spec(task_id).hypotheses
            lengths = [len(description.split()) for _, description in hypotheses]
            self.assertEqual(len(hypotheses), 6)
            self.assertLessEqual(max(lengths) - min(lengths), 6)
            alert = get_spec(task_id).alert
            self.assertNotIn('Cloudflare', alert)
            self.assertNotIn('GitHub', alert)
            self.assertNotIn('WAF regex', alert)
            self.assertNotIn('security-system deployment', alert)

    def test_reference_solution_passes_independent_replay_and_dashboard(self):
        for task_id in TASKS:
            with self.subTest(task=task_id):
                record = run_scripted(task_id)
                self.assertEqual(record['status'], 'completed')
                self.assertTrue(record['grade']['strict_pass'])
                verified = replay_record(record)
                self.assertTrue(verified['verified'], verified['warnings'])
                audit = audit_record(record)
                self.assertEqual(audit['status'], 'completed', audit['warnings'])
                self.assertTrue(audit['reference_matches'])
                self.assertTrue(audit['stored_grade_matches'])

    def test_wrong_cause_unsafe_repair_and_false_citations_fail(self):
        for task_id in TASKS:
            with self.subTest(task=task_id):
                for defect in ('wrong_cause','unsafe','empty_evidence'):
                    record = run_scripted(task_id, **{defect:True})
                    self.assertEqual(record['status'], 'completed')
                    self.assertFalse(record['grade']['strict_pass'], (task_id, defect))
                    self.assertTrue(replay_record(record)['verified'])
                    if defect=='unsafe':
                        self.assertTrue(record['grade']['unsafe_commit'])

    def test_evidence_provenance_accepts_mixed_sources_not_one_hidden_tool_pair(self):
        # Configuration + metrics was a valid model-visible evidence path that
        # the previous hidden config + (scan/topology/simulation) rule rejected.
        mixed = run_scripted(
            TASKS[0], final_evidence_tools=('inspect_config', 'inspect_metrics'),
        )
        self.assertTrue(mixed['grade']['strict_pass'])
        replayed = replay_record(mixed)
        self.assertTrue(replayed['verified'], replayed['warnings'])
        self.assertEqual(replayed['grade']['evidence_score'], 10)

        # Multiple citations do not create diversity when both observations
        # come from the same operational evidence category.
        one_category = run_scripted(
            TASKS[0], final_evidence_tools=('inspect_metrics', 'inspect_metrics'),
        )
        self.assertFalse(one_category['grade']['strict_pass'])
        replayed = replay_record(one_category)
        self.assertTrue(replayed['verified'], replayed['warnings'])
        self.assertEqual(replayed['grade']['evidence_score'], 5)

    def test_mutated_provider_trajectory_and_hashes_are_rejected(self):
        record = run_scripted(TASKS[0])
        forged = deepcopy(record)
        forged['trajectory'][0]['observation']['result']['alert'] = 'faked alert'
        self.assertFalse(replay_record(forged)['verified'])
        wrong_hash = deepcopy(record)
        wrong_hash['source_hashes']['oracle.py'] = '0'*64
        self.assertFalse(replay_record(wrong_hash)['verified'])
        self.assertEqual(set(implementation_hashes()), set(record['source_hashes']))

    def test_v6_reference_bundle_and_saved_record_endpoints(self):
        # A scripted reference episode validates API wiring only; delete it
        # immediately and NEVER count it as research/model evidence.
        from fastapi.testclient import TestClient
        from api.main import app
        from tasks import ROOT
        from zipfile import ZipFile
        from io import BytesIO
        filename = 'ui_v6cf_offline_test.jsonl'
        output = ROOT / 'results' / filename
        self.assertFalse(output.exists(), 'Never overwrite saved results')
        try:
            record = run_scripted(TASKS[0])
            output.write_text(json.dumps(record, ensure_ascii=False) + '\n', encoding='utf-8')
            client = TestClient(app)
            listing = client.get('/api/runs')
            self.assertEqual(listing.status_code, 200)
            self.assertIn(filename, [r['name'] for r in listing.json()])
            run = client.get(f'/api/runs/{filename}')
            self.assertEqual(run.status_code, 200)
            self.assertEqual(run.json()['rows'][0]['status'], 'completed')
            self.assertTrue(run.json()['rows'][0]['reference_verified'])
            bundle = client.get(f'/api/runs/{filename}/bundle.zip')
            self.assertEqual(bundle.status_code, 200)
            with ZipFile(BytesIO(bundle.content)) as z:
                files = set(z.namelist())
                self.assertIn('reference/v6-counterfactual/RW01.json', files)
                self.assertIn('benchmarks/v6_fixtures/counterfactual/RW01.json', files)
                self.assertIn('benchmarks/input_budget.py', files)
                self.assertNotIn('reference/RW01.json', files)
                self.assertNotIn('tasks/RW01.json', files)
        finally:
            output.unlink(missing_ok=True)

    def test_missing_reference_fails_review_without_changing_oracle(self):
        record = run_scripted(TASKS[0])
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            invalid = Path(tmp) / 'RW01.json'
            invalid.write_text(json.dumps({'failed_services':[], 'root_cause':'H99', 'fix_id':'A14'}))
            with patch('benchmarks.spec.reference_path', return_value=invalid):
                audit = audit_record(record)
            self.assertEqual(audit['status'], 'unverified')
            self.assertFalse(audit['reference_matches'])


if __name__ == '__main__':
    unittest.main()
