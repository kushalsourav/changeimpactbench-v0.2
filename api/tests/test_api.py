"""API regression tests; no OpenRouter requests are made."""
import json
from hashlib import sha256
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from api.main import app, file_path
from oracle import reference_answer, initial_failures
from tasks import load_cases, make_prompt

client = TestClient(app)


class EvidenceAPITests(unittest.TestCase):
    def test_health_never_exposes_secret(self):
        r = client.get('/api/health')
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('OPENROUTER_API_KEY', json.dumps(r.json()))

    def test_cases_and_oracle_are_correct(self):
        r = client.get('/api/tasks')
        self.assertEqual(r.status_code,200)
        self.assertEqual(len(r.json()),20)
        d = client.get('/api/tasks/T01').json()
        self.assertEqual(d['reference'],reference_answer(load_cases({'T01'})[0]))
        self.assertNotIn('"reference"',d['prompt'])
        direct, _ = initial_failures('T01', d['case']['facts'])
        self.assertEqual(d['direct_failed_services'], sorted(direct))
        self.assertTrue(all('direct_failed_after' in a for a in d['audit']['actions'].values()))

    def test_advanced_incidents_visible_and_repair_auditable(self):
        tasks = client.get('/api/tasks').json()
        advanced = [x for x in tasks if x.get('benchmark_version') == 'advanced-v0.4']
        self.assertEqual({x['id'] for x in advanced}, {'T06', 'T07'})
        for task_id in ('T06', 'T07'):
            response = client.get(f'/api/tasks/{task_id}')
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(len(data['case']['facts']['topology']), 32)
            self.assertEqual(data['audit']['actions']['A03']['failed_after'], [])
            self.assertEqual(data['reference']['fix_id'], 'A03')
            self.assertTrue(all('direct_failed_after' in a for a in data['audit']['actions'].values()))

    def test_v05_incidents_reachable_through_existing_api(self):
        listed = client.get('/api/tasks').json()
        causal = [t for t in listed if t.get('benchmark_version') == 'advanced-v0.5']
        self.assertEqual({t['id'] for t in causal}, {'T08', 'T09', 'T10', 'T11', 'T12'})
        for item in causal:
            with self.subTest(task=item['id']):
                result = client.get('/api/tasks/' + item['id'])
                self.assertEqual(result.status_code, 200)
                detail = result.json()
                self.assertEqual(detail['reference'], reference_answer(load_cases({item['id']})[0]))
                self.assertTrue(detail['audit']['actions'][detail['reference']['fix_id']]['full_recovery'])
                self.assertEqual(len(detail['direct_failed_services']), 2 if item['id'] in ('T08', 'T09') else 3)

    def test_mixing_benchmark_versions_is_rejected(self):
        from api.main import LaunchRequest
        from pydantic import ValidationError
        for ids in (['T01', 'T06'], ['T06', 'T08']):
            with self.assertRaises(ValidationError):
                LaunchRequest(models=['nvidia/nemotron-3-ultra-550b-a55b:free'], tasks=ids)

    def test_no_traversal_or_private_files(self):
        for name in ('.env', '_mock_test_only.jsonl', '../../.env', 'abc.log'):
            with self.assertRaises(Exception):
                file_path(name)

    def test_launch_requires_confirmation_and_key(self):
        request={'models':['nvidia/nemotron-3-ultra-550b-a55b:free'], 'tasks':['T01'], 'trials':1}
        self.assertEqual(client.post('/api/experiment/start',json=request).status_code,400)
        self.assertIn(client.post('/api/experiment/start',json={**request,'confirm':True}).status_code,(400,503)) if not client.get('/api/health').json()['key_configured'] else None

    def test_illegal_models_and_budgets(self):
        for body in ({'models':['openrouter/auto'], 'tasks':['T01'], 'confirm':True},
                     {'models':['provider/model:free'], 'tasks':['T01'], 'trials':200, 'confirm':True},
                     {'models':['provider/model:free'], 'tasks':['T99'], 'confirm':True}):
            self.assertEqual(client.post('/api/experiment/start',json=body).status_code,422)

    def test_saved_jsonl_is_regraded(self):
        task = load_cases({'T01'})[0]
        raw = json.dumps(reference_answer(task))
        entry = {'task_id':'T01','model_requested':'test/mock:free','model_returned':'test/mock:free','trial':1,
                 'status':'completed','raw_output':raw, 'finish_reason':'stop','prompt':make_prompt(task),
                 'prompt_sha256':sha256(make_prompt(task).encode()).hexdigest(),
                 'grade':{'pass':False,'score':0}}
        path=ROOT/'results'/'api_smoketest.jsonl'
        try:
            path.write_text(json.dumps(entry)+'\n',encoding='utf-8')
            data=client.get('/api/runs/api_smoketest.jsonl').json()
            self.assertEqual(data['summary'][0]['passed'],1)
            self.assertTrue(data['rows'][0]['grade_verified'] is False)
            response=client.get('/api/runs/api_smoketest.jsonl/records/0').json()
            self.assertTrue(response['audit']['grade']['pass'])
        finally:
            path.unlink(missing_ok=True)

if __name__ == '__main__':
    unittest.main()

class ExportContractTests(unittest.TestCase):
    def test_new_exports_are_real_and_bounded(self):
        task = load_cases({'T01'})[0]
        rec = {'task_id':'T01','model_requested':'mock/test:free','trial':1,
               'status':'completed','raw_output':json.dumps(reference_answer(task)),
               'prompt_sha256':sha256(make_prompt(task).encode()).hexdigest()}
        path=ROOT/'results'/'api_exports_test.jsonl'
        try:
            path.write_text(json.dumps(rec)+'\n',encoding='utf-8')
            audit=client.get('/api/runs/api_exports_test.jsonl/audit.json')
            self.assertEqual(audit.status_code,200)
            self.assertEqual(audit.json()['records'][0]['audit']['grade']['score'],1)
            bundle=client.get('/api/runs/api_exports_test.jsonl/bundle.zip')
            self.assertEqual(bundle.status_code,200)
            import zipfile,io
            with zipfile.ZipFile(io.BytesIO(bundle.content)) as z:
                self.assertIn('results/api_exports_test.jsonl',z.namelist())
                self.assertIn('oracle.py',z.namelist())
                self.assertNotIn('.env',z.namelist())
        finally:
            path.unlink(missing_ok=True)

    def test_stop_requires_active_run(self):
        self.assertEqual(client.post('/api/experiment/stop').status_code,409)


class FrontendContractTests(unittest.TestCase):
    def test_run_metadata_is_named_and_versioned(self):
        case = load_cases({'T06'})[0]
        r = {'task_id':'T06','model_requested':'test/mock:free',
             'benchmark_version':'advanced-v0.4','trial':1,'status':'completed',
             'prompt_sha256':sha256(make_prompt(case).encode()).hexdigest(),
             'finish_reason':'stop','raw_output':json.dumps(reference_answer(case))}
        target = ROOT / 'results' / 'ui_contract_smoke.jsonl'
        try:
            target.write_text(json.dumps(r) + '\n', encoding='utf-8')
            catalog = client.get('/api/runs').json()
            item = next(x for x in catalog if x['name']=='ui_contract_smoke.jsonl')
            self.assertEqual(item['benchmark_versions'], ['advanced-v0.4'])
            self.assertEqual(item['tasks'], ['T06'])
            detail = client.get('/api/runs/ui_contract_smoke.jsonl').json()
            self.assertEqual(detail['benchmark_versions'], ['advanced-v0.4'])
            self.assertEqual(detail['rows'][0]['score'],1.0)
        finally:
            target.unlink(missing_ok=True)

    def test_status_includes_durable_progress_fields(self):
        from unittest.mock import patch
        from api import main as backend
        from types import SimpleNamespace
        target = ROOT / 'results' / 'ui_progress_smoke.log'
        try:
            target.write_text('[1/2] test/model:free T06 trial=1 ...\n    score=1.0, pass=True\n'
                              + 'non-progress diagnostic ' * 1000 + '\n'
                              + '[2/2] test/model:free T07 trial=1 ...\n', encoding='utf-8')
            fake = SimpleNamespace(poll=lambda: None)
            with patch.dict(backend.active, {'process':fake,'log_path':target,'output_file':'ui_none.jsonl',
                     'id':'demo', 'started_utc':'2026-11-02T00:00:00+00:00','requests_planned':2}, clear=True):
                response = client.get('/api/experiment/status').json()
                self.assertEqual(response['requests_started'],2)
                self.assertEqual(response['requests_finished'],1)
                self.assertIn('T07 trial=1',response['current_request'])
                self.assertEqual(response['records_saved'],0)
        finally:
            target.unlink(missing_ok=True)

class LiveTimingTests(unittest.TestCase):
    def test_elapsed_is_monotonic_and_freezes_when_run_exits(self):
        from unittest.mock import patch
        from api import main as backend
        from types import SimpleNamespace

        target = ROOT / 'results' / 'ui_timer_smoke.log'
        fake = SimpleNamespace(code=None)
        fake.poll = lambda: fake.code
        try:
            target.write_text('[1/1] test/model:free T08 trial=1 ...\n', encoding='utf-8')
            active_run = {
                'process': fake, 'log_path': target, 'output_file': 'ui_none.jsonl',
                'id': 'timer-test', 'started_utc': '2026-11-03T00:00:00+00:00',
                'started_monotonic': 100.0, 'requests_planned': 1,
            }
            with patch.dict(backend.active, active_run, clear=True):
                with patch.object(backend.time, 'monotonic', return_value=112.3):
                    live = client.get('/api/experiment/status').json()
                self.assertEqual(live['status'], 'running')
                self.assertAlmostEqual(live['elapsed_seconds'], 12.3)

                fake.code = 0
                with patch.object(backend.time, 'monotonic', return_value=114.7):
                    finished = client.get('/api/experiment/status').json()
                self.assertEqual(finished['status'], 'finished')
                self.assertAlmostEqual(finished['elapsed_seconds'], 14.7)

                with patch.object(backend.time, 'monotonic', return_value=118.0):
                    again = client.get('/api/experiment/status').json()
                self.assertEqual(again['elapsed_seconds'], finished['elapsed_seconds'])
        finally:
            target.unlink(missing_ok=True)


class ExperimentManifestTests(unittest.TestCase):
    def test_manifest_records_planned_trials_even_if_run_stops_early(self):
        import os
        from unittest.mock import patch
        from types import SimpleNamespace
        from api import main as backend

        model = 'nvidia/nemotron-3-ultra-550b-a55b:free'
        request = {
            'models': [model],
            'tasks': ['T06', 'T07'],
            'trials': 3,
            'confirm': True,
        }
        fake = SimpleNamespace(poll=lambda: None)
        original_active = dict(backend.active)
        output_file = None
        try:
            with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'only-for-offline-test'}), \
                    patch.object(backend, 'valid_models', return_value=[{'id': model, 'name': 'Nemotron'}]), \
                    patch.object(backend.subprocess, 'Popen', return_value=fake):
                response = client.post('/api/experiment/start', json=request)
            self.assertEqual(response.status_code, 202, response.text)
            self.assertEqual(response.json()['elapsed_seconds'], 0.0)
            self.assertTrue(response.json()['started_utc'].endswith('+00:00'))
            output_file = response.json()['output_file']
            manifest = backend.run_manifest(output_file)
            self.assertEqual(manifest['trials'], 3)
            self.assertEqual(manifest['benchmark_version'], 'advanced-v0.4')
            self.assertEqual(manifest['requests_planned'], 6)
            self.assertNotIn('only-for-offline-test', json.dumps(manifest))

            case = load_cases({'T06'})[0]
            record = {
                'task_id': 'T06',
                'model_requested': model,
                'trial': 1,
                'status': 'completed',
                'raw_output': json.dumps(reference_answer(case)),
                'prompt_sha256': sha256(make_prompt(case).encode()).hexdigest(),
            }
            (ROOT / 'results' / output_file).write_text(json.dumps(record) + '\n')
            data = client.get(f'/api/runs/{output_file}').json()
            self.assertEqual(data['expected_trials'], 3)
            self.assertEqual(data['expected_trials_source'], 'recorded-at-launch')
            self.assertIsNone(data['summary'][0]['pass_power_k'])
            self.assertEqual(data['summary'][0]['full_trial_groups'], 0)
            bundle = client.get(f'/api/runs/{output_file}/bundle.zip')
            self.assertEqual(bundle.status_code, 200)
            import io, zipfile
            with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
                names = archive.namelist()
                self.assertIn('tasks/T06.json', names)
                self.assertNotIn('tasks/T01.json', names)
                self.assertIn('run_eval.py', names)
                self.assertIn('results/' + output_file.replace('.jsonl', '.manifest.json'), names)
        finally:
            backend.active.clear()
            backend.active.update(original_active)
            if output_file:
                for suffix in ('.jsonl', '.log', '.manifest.json'):
                    (ROOT / 'results' / output_file.replace('.jsonl', suffix)).unlink(missing_ok=True)

    def test_historical_file_reports_inferred_trial_count(self):
        case = load_cases({'T01'})[0]
        record = {
            'task_id': 'T01',
            'model_requested': 'test/mock:free',
            'trial': 2,
            'status': 'completed',
            'raw_output': json.dumps(reference_answer(case)),
        }
        filename = 'historical_trial_count_test.jsonl'
        path = ROOT / 'results' / filename
        try:
            path.write_text(json.dumps(record) + '\n')
            result = client.get('/api/runs/' + filename).json()
            self.assertEqual(result['expected_trials'], 2)
            self.assertEqual(result['expected_trials_source'], 'inferred-from-records')
        finally:
            path.unlink(missing_ok=True)
if __name__ == "__main__":
    unittest.main()

class AgenticAPITests(unittest.TestCase):
    def test_agentic_task_and_reviewer_view_are_separate(self):
        listed = client.get('/api/tasks').json()
        items = [t for t in listed if t['id']=='AG08']
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['condition'],'agentic')
        detail = client.get('/api/tasks/AG08').json()
        self.assertFalse(detail['reference_visible_to_agent'])
        self.assertEqual(detail['reference'],reference_answer(load_cases({'T08'})[0]))
        self.assertNotIn('"fix_id": "A03"',detail['prompt'])

    def test_agentic_launch_cannot_be_single_turn_or_multi_model(self):
        from api.main import LaunchRequest
        model='nvidia/nemotron-3-ultra-550b-a55b:free'
        body={'models':[model], 'tasks':['AG08'], 'condition':'single-turn', 'confirm':True}
        # Validation of the requested condition happens without provider calls.
        from unittest.mock import patch
        with patch.dict(__import__('os').environ, {'OPENROUTER_API_KEY':'offline-only'}), \
             patch('api.main.valid_models',return_value=[{'id':model}]):
            self.assertEqual(client.post('/api/experiment/start',json=body).status_code,400)
            self.assertEqual(client.post('/api/experiment/start',json={**body,'condition':'agentic','trials':2}).status_code,400)
            self.assertEqual(client.post('/api/experiment/start',json={**body,'condition':'agentic','models':[model, 'cohere/model:free']}).status_code,400)

    def test_offline_agentic_record_is_replayed_in_all_views(self):
        from tests.test_agentic import offline_record
        from api.main import run_manifest_path
        record=offline_record()
        record.update({'model_requested':'mock/offline:free', 'trial':1,
                       'finish_reason':'stop','timestamp_utc':'2026-11-03T10:00:00+00:00'})
        record['grade']=__import__('agentic').replay_record(record)['grade']
        file='agentic_api_offline.jsonl'
        path=ROOT/'results'/file
        try:
            path.write_text(json.dumps(record)+'\n',encoding='utf-8')
            info=client.get('/api/runs/'+file).json()
            self.assertEqual(info['rows'][0]['condition'],'agentic')
            self.assertTrue(info['rows'][0]['pass'])
            self.assertEqual(info['summary'][0]['passed'],1)
            self.assertEqual(info['benchmark_versions'],['agentic-ag08-v1'])
            detail=client.get('/api/runs/'+file+'/records/0').json()
            self.assertTrue(detail['audit']['stored_grade_matches'])
            self.assertTrue(detail['audit']['grade']['strict_pass'])
            self.assertEqual(detail['diagnosis']['missed_services'],[])
            bundle=client.get('/api/runs/'+file+'/bundle.zip')
            self.assertEqual(bundle.status_code,200)
            import zipfile,io
            with zipfile.ZipFile(io.BytesIO(bundle.content)) as z:
                self.assertIn('agentic.py',z.namelist())
                self.assertIn('run_agentic.py',z.namelist())
                self.assertIn('tasks/T08.json',z.namelist())
                self.assertNotIn('.env',z.namelist())
        finally:
            path.unlink(missing_ok=True)
            run_manifest_path(file).unlink(missing_ok=True)

    def test_agentic_manifest_and_command_are_bounded(self):
        import os
        from unittest.mock import patch
        from types import SimpleNamespace
        from api import main as backend
        model = 'nvidia/nemotron-3-ultra-550b-a55b:free'
        fake = SimpleNamespace(poll=lambda: None)
        previous=dict(backend.active)
        filename=None
        try:
            with patch.dict(os.environ, {'OPENROUTER_API_KEY':'offline'}), \
                 patch.object(backend,'valid_models',return_value=[{'id':model}]), \
                 patch.object(backend.subprocess,'Popen',return_value=fake) as launch:
                r=client.post('/api/experiment/start',json={
                    'models':[model],'tasks':['AG08'],'condition':'agentic',
                    'trials':1,'confirm':True})
            self.assertEqual(r.status_code,202,r.text)
            filename=r.json()['output_file']
            command=launch.call_args.args[0]
            self.assertTrue(any(str(s).endswith('run_agentic.py') for s in command))
            manifest=backend.run_manifest(filename)
            self.assertEqual(manifest['condition'],'agentic')
            self.assertEqual(manifest['requests_planned'],24)
            self.assertTrue(manifest['planned_provider_requests_are_upper_bound'])
        finally:
            backend.active.clear()
            backend.active.update(previous)
            if filename:
                for ext in ('.jsonl','.log','.manifest.json'):
                    (ROOT/'results'/filename.replace('.jsonl',ext)).unlink(missing_ok=True)

class AgenticSafetyAndProgressTests(unittest.TestCase):
    def test_agentic_live_progress_counts_provider_turns(self):
        from unittest.mock import patch
        from api import main as backend
        from types import SimpleNamespace
        output = ROOT / 'results' / 'agentic_status_offline.log'
        try:
            output.write_text(
                '[1/1] offline AG08 trial=1\n'
                '    turn=1/24 · provider request ...\n'
                '    EV001 read_alert → {"time":"14:10 UTC"}\n'
                '    turn=2/24 · provider request ...\n', encoding='utf-8')
            active_run={'id':'offline','process':SimpleNamespace(poll=lambda:None),
                        'log_path':output,'output_file':'ui_missing.jsonl',
                        'started_utc':'2026-11-03T10:00:00+00:00',
                        'requests_planned':24, 'condition':'agentic'}
            with patch.dict(backend.active,active_run,clear=True):
                state=client.get('/api/experiment/status').json()
            self.assertEqual(state['requests_started'],2)
            self.assertEqual(state['requests_finished'],1)
            self.assertEqual(state['current_request'],'Agent tool turn 2 of 24')
            self.assertEqual(state['condition'],'agentic')
        finally:
            output.unlink(missing_ok=True)

    def test_verified_unsafe_commit_kept_even_if_model_truncates_after_action(self):
        from agentic import AgentEnvironment, TASK_ID, VERSION, agent_prompt, digest, source_case, implementation_hashes
        env=AgentEnvironment()
        for tool,args in [('read_alert',{}),('apply_repair',{'action_id':'A04'})]:
            env.execute(tool,args)
            env.steps[-1]['raw_model_output']=json.dumps({'tool':tool,'arguments':args})
        record={'task_id':TASK_ID,'benchmark_version':VERSION,
                'prompt_sha256':sha256(agent_prompt().encode()).hexdigest(),
                'case_sha256':digest(source_case()), 'source_hashes':implementation_hashes(),
                'trajectory':env.steps,'status':'incomplete_generation','raw_output':'',
                'committed_effect':env.committed_effect,'final_diagnosis':None,
                'model_requested':'mock/offline:free','trial':1}
        file='agentic_unsafe_partial_test.jsonl'
        path=ROOT/'results'/file
        try:
            path.write_text(json.dumps(record)+'\n',encoding='utf-8')
            info=client.get('/api/runs/'+file).json()
            self.assertEqual(info['rows'][0]['status'],'incomplete_generation')
            self.assertTrue(info['rows'][0]['unsafe_commit'])
            self.assertIsNone(info['rows'][0]['score'])
            self.assertEqual(info['counts']['unsafe_committed_episodes'],1)
        finally:
            path.unlink(missing_ok=True)


class AgenticV2APITests(unittest.TestCase):
    """Version-isolated browser contract; all provider launches are mocked."""

    def test_v2_task_and_prompt_are_separate_from_reviewer_reference(self):
        listed = client.get('/api/tasks').json()
        self.assertEqual({t['id'] for t in listed if t.get('condition') == 'agentic'},
                         {'AG08', 'AG08V2', 'AG08V3', 'AG08V4', 'AG09', 'AG10', 'AG11', 'AG12'})
        detail = client.get('/api/tasks/AG08V2').json()
        self.assertEqual(detail['case']['id'], 'AG08V2')
        self.assertEqual(detail['case']['benchmark_version'], 'agentic-ag08-v2')
        self.assertFalse(detail['reference_visible_to_agent'])
        self.assertEqual(detail['reference'], reference_answer(load_cases({'T08'})[0]))
        self.assertNotIn('North gateway trust lags', detail['prompt'])
        self.assertNotIn('west ledger is below', detail['prompt'])

    def test_agentic_versions_cannot_be_mixed(self):
        from api.main import LaunchRequest
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            LaunchRequest(models=['mock/runner:free'], tasks=['AG08', 'AG08V2'],
                          condition='agentic')
        with self.assertRaises(ValidationError):
            LaunchRequest(models=['mock/runner:free'], tasks=['T08', 'AG08V2'])

    def test_v2_launch_uses_its_own_runner_and_immutable_manifest(self):
        import os
        from unittest.mock import patch
        from types import SimpleNamespace
        from api import main as backend
        model = 'mock/audit:free'
        fake = SimpleNamespace(poll=lambda: None)
        prior = dict(backend.active)
        filename = None
        try:
            with patch.dict(os.environ, {'OPENROUTER_API_KEY':'offline-only'}), \
                 patch.object(backend, 'valid_models', return_value=[{'id':model}]), \
                 patch.object(backend.subprocess, 'Popen', return_value=fake) as process:
                r = client.post('/api/experiment/start', json={
                    'models':[model], 'tasks':['AG08V2'], 'condition':'agentic',
                    'trials':1, 'confirm':True,
                })
            self.assertEqual(r.status_code, 202, r.text)
            filename = r.json()['output_file']
            command = process.call_args.args[0]
            self.assertTrue(any('run_agentic_v2.py' in part for part in command))
            manifest = backend.run_manifest(filename)
            self.assertEqual(manifest['benchmark_version'], 'agentic-ag08-v2')
            self.assertEqual(manifest['requests_planned'], 24)
            self.assertEqual(manifest['schema_version'], 3)
            self.assertIn('agentic_v2.py', manifest['agentic_source_hashes'])
            self.assertNotIn('offline-only', json.dumps(manifest))
        finally:
            backend.active.clear()
            backend.active.update(prior)
            if filename:
                for suffix in ('.jsonl', '.log', '.manifest.json'):
                    (ROOT / 'results' / filename.replace('.jsonl', suffix)).unlink(missing_ok=True)

    def test_saved_v2_record_is_regraded_in_results_traces_and_bundle(self):
        from tests.test_agentic_v2 import fake_run
        from agentic_v2 import reference_trajectory
        from copy import deepcopy
        import io
        import zipfile
        actions = reference_trajectory()
        actions.insert(-2, deepcopy(actions[-1]))
        record = fake_run(actions)
        record['trial'] = 1
        record['model_requested'] = 'mock/audit:free'
        filename = 'agentic_v2_api_test.jsonl'
        path = ROOT / 'results' / filename
        try:
            path.write_text(json.dumps(record)+'\n', encoding='utf-8')
            data = client.get(f'/api/runs/{filename}').json()
            self.assertEqual(data['benchmark_versions'], ['agentic-ag08-v2'])
            self.assertTrue(data['rows'][0]['pass'])
            self.assertEqual(data['rows'][0]['score'], .98)
            self.assertEqual(data['rows'][0]['condition'], 'agentic')
            item = client.get(f'/api/runs/{filename}/records/0').json()
            self.assertTrue(item['audit']['stored_grade_matches'])
            self.assertEqual(item['audit']['grade']['procedure_score'], 8)
            self.assertEqual(len(item['audit']['grade']['protocol_errors']), 1)
            self.assertEqual(item['diagnosis']['missed_services'], [])
            exported = client.get(f'/api/runs/{filename}/bundle.zip')
            self.assertEqual(exported.status_code, 200)
            with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
                self.assertIn('agentic_v2.py', archive.namelist())
                self.assertIn('run_agentic_v2.py', archive.namelist())
                self.assertIn('tasks/T08.json', archive.namelist())
                self.assertNotIn('.env', archive.namelist())
        finally:
            path.unlink(missing_ok=True)
