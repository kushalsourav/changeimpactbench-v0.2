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
from benchmarks.spec import reference_path, source_case, service_codes, get_spec, reference_trajectory
from benchmarks.grader import replay_record
from benchmarks.environment import AgentEnvironment
from dashboard_data import audit_record
from oracle import reference_answer, simulate, patch_facts
from run_graph_agent import run_episode

TASKS = [f'RW{i:02}V6CF' for i in range(1, 7)]


class ScriptedReferenceGraph:
    """Deterministic oracle tool emitter; NEVER scored as an actual AI provider."""
    def __init__(self, env, *, wrong_cause=False, unsafe=False, empty_evidence=False):
        self.env = env
        self.wrong_cause = wrong_cause
        self.unsafe = unsafe
        self.empty_evidence = empty_evidence

    def stream(self, _input, config, stream_mode):
        for idx, (tool, arguments) in enumerate(reference_trajectory(self.env.task_id), 1):
            args = deepcopy(arguments)
            if self.wrong_cause and tool == 'submit_diagnosis':
                args['root_cause_id'] = 'H01' if args['root_cause_id'] != 'H01' else 'H02'
            if self.unsafe and tool == 'apply_repair':
                args['action_id'] = 'A90'
            if self.empty_evidence and tool == 'submit_diagnosis':
                args['evidence_ids'] = ['EV001', 'EV002']
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


class V6CounterfactualTests(unittest.TestCase):
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
                self.assertEqual(reference_path(task_id).parent.name, 'v6-counterfactual')

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
                env.execute('read_alert', {})
                scan = env.execute('scan_service_health', {})['result']
                self.assertLess(scan['observed_count'], scan['service_count'])
                codes = service_codes(task_id)
                observed = {n for n,c in codes.items()
                            if env.execute('inspect_metrics', {'service':c})['result']['health_probe']=='unavailable'}
                self.assertEqual(observed, set(reference_answer(source_case(task_id))['failed_services']))

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
                self.assertNotIn('reference/RW01.json', files)
                self.assertNotIn('tasks/RW01.json', files)
        finally:
            output.unlink(missing_ok=True)

    def test_missing_reference_fails_review_without_changing_oracle(self):
        record = run_scripted(TASKS[0])
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            invalid = Path(tmp) / 'RW01.json'
            invalid.write_text(json.dumps({'failed_services':[], 'root_cause':'H99', 'fix_id':'A95'}))
            with patch('benchmarks.spec.reference_path', return_value=invalid):
                audit = audit_record(record)
            self.assertEqual(audit['status'], 'unverified')
            self.assertFalse(audit['reference_matches'])


if __name__ == '__main__':
    unittest.main()
