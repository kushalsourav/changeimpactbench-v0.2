"""Local-only v0.8 research contract tests. No live OpenRouter requests."""
import io
import json
from pathlib import Path
import unittest
from zipfile import ZipFile
from unittest.mock import patch

from fastapi.testclient import TestClient
from api import main as server
from agentic_v3 import reference_trajectory, agent_prompt
from run_agentic_v3 import run_episode
from tasks import ROOT

client = TestClient(server.app)


def offline_episode(actions, serial):
    turns = iter(actions)
    def request(_url, _token, _body):
        name, args = next(turns)
        return {
            'id': f'v08-mock-{serial}', 'model': 'mock/test:free',
            'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({'tool': name, 'arguments': args})}}],
            'usage': {'prompt_tokens': 3, 'completion_tokens': 3},
        }
    return run_episode('mock/test:free', 1, 'offline-no-keys', 1024, 'low', 0, 0, request)


class V08ResearchContractTests(unittest.TestCase):
    def test_task_catalog_and_explicit_objective_without_reference_leak(self):
        tasks = client.get('/api/tasks').json()
        self.assertEqual({t['id'] for t in tasks if t.get('condition') == 'agentic'},
                         {'AG08', 'AG08V2', 'AG08V3', 'AG08V4', 'AG09', 'AG10', 'AG11', 'AG12'})
        data = client.get('/api/tasks/AG08V3').json()
        self.assertEqual(data['case']['benchmark_version'], 'agentic-ag08-v3')
        self.assertFalse(data['reference_visible_to_agent'])
        self.assertIn('Restore ALL initially unavailable', agent_prompt())
        self.assertIn('Partial recovery does NOT meet the objective', agent_prompt())
        self.assertNotIn('A03', agent_prompt())
        self.assertNotIn('gateway-north trust', agent_prompt().lower())
        self.assertEqual(client.get('/api/tasks/AG08V2').json()['case']['benchmark_version'], 'agentic-ag08-v2')

    def test_saved_v3_regrades_and_cannot_pool_versions(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            server.LaunchRequest(models=['mock/test:free'], tasks=['AG08V2', 'AG08V3'], condition='agentic')
        ok = offline_episode(reference_trajectory(), 'ok')
        self.assertEqual(ok['status'], 'completed')
        self.assertTrue(ok['grade']['strict_pass'])
        path = ROOT / 'results' / 'ui_v08_regrade_test.jsonl'
        try:
            path.write_text(json.dumps(ok) + '\n', encoding='utf-8')
            info = client.get('/api/runs/' + path.name).json()
            self.assertEqual(info['rows'][0]['score'], 1.0)
            self.assertTrue(info['rows'][0]['grade_verified'])
            details = client.get('/api/runs/' + path.name + '/records/0').json()
            self.assertEqual(details['audit']['grade']['strict_pass'], True)
            self.assertTrue(details['audit']['prompt_sha_matches'])
            self.assertTrue(details['audit']['reference_matches'])
            with ZipFile(io.BytesIO(client.get('/api/runs/' + path.name + '/bundle.zip').content)) as z:
                self.assertIn('agentic_v3.py', z.namelist())
                self.assertIn('run_agentic_v3.py', z.namelist())
                self.assertNotIn('.env', z.namelist())
        finally:
            path.unlink(missing_ok=True)

    def test_cross_run_aggregation_uses_frozen_version_and_settings(self):
        good = offline_episode(reference_trajectory(), 'pass')
        # Same simulator, same source, but a deliberately partial non-disruptive repair.
        wrong_actions = [(name, {'action_id':'A02'} if name in ('apply_repair','simulate_repair')
                          else {**args, 'fix_id':'A02'} if name == 'submit_diagnosis'
                          else args) for name, args in reference_trajectory()]
        bad = offline_episode(wrong_actions, 'partial')
        self.assertFalse(bad['grade']['strict_pass'])
        self.assertFalse(bad['grade']['unsafe_commit'])
        self.assertFalse(bad['grade']['recovery_success'])
        names = ['ui_v08_cross_one.jsonl', 'ui_v08_cross_two.jsonl']
        try:
            for filename, record in zip(names, (good, bad)):
                (ROOT/'results'/filename).write_text(json.dumps(record)+'\n',encoding='utf-8')
            data = client.get('/api/agentic/comparison?task_id=AG08V3').json()
            grp = next(x for x in data['groups'] if x['model'] == 'mock/test:free')
            self.assertEqual(grp['episodes'], 2)
            self.assertEqual(grp['completed'], 2)
            self.assertEqual(grp['strict_passes'], 1)
            self.assertEqual(grp['incomplete_repairs'], 1)
            self.assertEqual(grp['unsafe_commits'], 0)
            self.assertEqual(grp['strict_pass_rate_completed'], .5)
            self.assertEqual({e['run'] for e in grp['evidence']}, set(names))
            self.assertEqual(client.get('/api/agentic/comparison?task_id=AG08V2').json()['task_id'], 'AG08V2')
            self.assertEqual(client.get('/api/agentic/comparison?task_id=T08').status_code, 400)
        finally:
            for name in names:
                (ROOT/'results'/name).unlink(missing_ok=True)

    def test_human_review_is_separate_hash_bound_and_not_auto_verified(self):
        record = offline_episode(reference_trajectory(), 'review')
        filename = 'ui_v08_human_review.jsonl'
        target = ROOT / 'results' / filename
        sidecar = ROOT / 'results' / 'ui_v08_human_review.reviews.json'
        body = {'status':'verified','reviewer':'Independent reviewer',
                'notes':'Confirmed T08 oracle and tool evidence against source configuration.',
                'oracle_checked': True, 'task_grader_alignment_checked': True,
                'evidence_support_checked': True}
        try:
            target.write_text(json.dumps(record) + '\n', encoding='utf-8')
            rec = client.get(f'/api/runs/{filename}/records/0').json()
            self.assertIsNone(rec['human_review'])
            self.assertEqual(client.get(f'/api/runs/{filename}').json()['counts']['human_reviews_pending'], 1)
            resp = client.post(f'/api/runs/{filename}/records/0/review', json={**body, 'evidence_support_checked':False})
            self.assertEqual(resp.status_code, 422)
            self.assertEqual(client.post(f'/api/runs/{filename}/records/0/review', json=body).status_code, 200)
            rec = client.get(f'/api/runs/{filename}/records/0').json()
            self.assertEqual(rec['human_review']['status'], 'verified')
            counts = client.get(f'/api/runs/{filename}').json()['counts']
            self.assertEqual(counts['human_reviews_pending'], 0)
            self.assertEqual(counts['human_reviews_verified'], 1)
            with ZipFile(io.BytesIO(client.get(f'/api/runs/{filename}/bundle.zip').content)) as z:
                self.assertIn('results/ui_v08_human_review.reviews.json', z.namelist())
            # If model evidence changes, stale review must NOT look verified.
            target.write_text(json.dumps({**record, 'trial': 2})+'\n', encoding='utf-8')
            self.assertIsNone(client.get(f'/api/runs/{filename}/records/0').json()['human_review'])
            self.assertEqual(client.get(f'/api/runs/{filename}').json()['counts']['human_reviews_pending'], 1)
        finally:
            target.unlink(missing_ok=True)
            sidecar.unlink(missing_ok=True)

    def test_launch_plan_uses_new_runner_without_provider_call(self):
        from unittest.mock import MagicMock
        model='nvidia/nemotron-3-ultra-550b-a55b:free'
        with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'fake-offline-only'}), \
             patch.object(server,'valid_models',return_value=[{'id': model}]), \
             patch.object(server.subprocess, 'Popen') as spawn:
            spawn.return_value.poll.return_value = 0
            response=client.post('/api/experiment/start', json={'models':[model], 'tasks':['AG08V3'],
                'trials':1,'confirm':True,'condition':'agentic'})
            self.assertEqual(response.status_code,202, response.text)
            args = spawn.call_args.args[0]
            self.assertIn('run_agentic_v3.py', ' '.join(args))
            manifest=server.run_manifest(response.json()['output_file'])
            self.assertEqual(manifest['benchmark_version'],'agentic-ag08-v3')
            self.assertIn('agentic_v3.py', manifest['agentic_source_hashes'])
            (ROOT/'results'/response.json()['output_file']).unlink(missing_ok=True)
            (ROOT/'results'/f"{Path(response.json()['output_file']).stem}.manifest.json").unlink(missing_ok=True)
            (ROOT/'results'/f"{Path(response.json()['output_file']).stem}.log").unlink(missing_ok=True)
            server.active.clear()
