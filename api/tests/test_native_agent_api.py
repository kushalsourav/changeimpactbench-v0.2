"""Native-only API contracts, real replay endpoints and authorization boundary.

All model messages in this file are TEST DOUBLE traffic, not empirical trials.
"""
from __future__ import annotations
from copy import deepcopy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from fastapi.testclient import TestClient
from api.main import app, LaunchRequest, file_path
from agent_graph import TASK_IDS, VERSIONS, GRAPH_BASE, agent_prompt, GraphEnvironment
from benchmarks.spec import REGISTRY, reference_trajectory
from run_graph_agent import run_episode
from tasks import ROOT
from types import SimpleNamespace

client = TestClient(app)


class FakeGraph:
    """Offline reference trajectory test double; no provider API requests."""
    def __init__(self, env: GraphEnvironment):
        self.env=env
    def stream(self, _input, config, stream_mode):
        assert stream_mode=='updates'
        for index,(tool,args) in enumerate(reference_trajectory(self.env.task_id),1):
            uid=f'fake-test-{index}'
            yield {'model':{'messages':[SimpleNamespace(type='ai',content='',
                tool_calls=[{'name':tool,'args':args,'id':uid}],
                usage_metadata={'input_tokens':3,'output_tokens':4},
                response_metadata={'model_name':'mock/test:free','finish_reason':'tool_calls'},
                additional_kwargs={},id=uid)]}}
            obs=self.env.execute(tool,args,uid)
            yield {'tools':{'messages':[SimpleNamespace(type='tool',content=obs)]}}


def fake_graph(env, *_args):
    return FakeGraph(env)


class NativeAgentAPIContracts(unittest.TestCase):
    def test_only_five_synthetic_langgraph_cases_and_48_call_budget(self):
        out=client.get('/api/tasks')
        self.assertEqual(out.status_code,200)
        cases=out.json()
        self.assertEqual({c['id'] for c in cases},{f'RW{i:02d}{suffix}' for i in range(1,7) for suffix in ('V4','V6CF')})
        self.assertEqual(len(cases),12)
        for task in cases:
            self.assertEqual(task['condition'],'agentic')
            if task['id'].endswith(('V6N','V6CF','V5')):
                self.assertIn('synthetic',task['dataset_origin'])
                self.assertEqual(task['source_url'],'')
            else:
                self.assertIn('public',task['dataset_origin'])
                self.assertTrue(task['source_url'].startswith('https://'))
            self.assertTrue(task['source_seed'].startswith(tuple(f'RW{i:02}' for i in range(1,7))))
            self.assertEqual(task['benchmark_version'],VERSIONS[task['id']])
            details=client.get('/api/tasks/'+task['id']).json()
            self.assertEqual(details['prompt'],agent_prompt(task['id']))
            self.assertFalse(details['reference_visible_to_agent'])
            self.assertIn('48 model requests',details['prompt'])
            self.assertNotIn(details['reference']['fix_id'],details['prompt'])
        self.assertEqual(client.get('/api/tasks/T01').status_code,404)
        self.assertEqual(client.get('/api/tasks/AG08V6').status_code,404)
        self.assertEqual(client.get('/api/agentic/comparison?task_id=AG08V6').status_code,400)

    def test_only_native_launch_is_accepted_and_requires_approval(self):
        model='nvidia/nemotron-3-ultra-550b-a55b:free'
        self.assertEqual(LaunchRequest(models=[model],tasks=['RW01V4']).condition,'agentic')
        req={'models':[model],'tasks':['RW01V4'],'trials':1,'confirm':False}
        self.assertEqual(client.post('/api/experiment/start',json=req).status_code,400)
        self.assertEqual(client.post('/api/experiment/start',json={**req,'condition':'single-turn'}).status_code,422)
        self.assertEqual(client.post('/api/experiment/start',json={**req,'tasks':['AG08V6']}).status_code,422)
        self.assertEqual(client.post('/api/experiment/start',json={**req,'trials':6}).status_code,422)
        self.assertEqual(client.post('/api/experiment/start',json={**req,'models':[model,model]}).status_code,422)
        # Key missing: no OpenRouter call can start during tests.
        with patch.dict('os.environ',{'OPENROUTER_API_KEY':''}):
            self.assertEqual(client.post('/api/experiment/start',json={**req,'confirm':True}).status_code,400)
        self.assertIn("ROOT / 'tools/run_mixed_providers.py'",(ROOT/'api/routes/experiment.py').read_text())
        self.assertIn("ROOT / 'run_graph_agent.py'",(ROOT/'tools/run_mixed_providers.py').read_text())

    def test_evidence_verification_exports_and_regrade_from_native_trace(self):
        record=run_episode('RW01V3','mock/test:free',1,'test-only-token',2048,'low',0,3,graph_factory=fake_graph)
        self.assertEqual(record['status'],'completed')
        self.assertTrue(record['grade']['strict_pass'])
        filename='ui_offline_contract_test.jsonl'
        path=ROOT/'results'/filename
        review_path=ROOT/'results'/'ui_offline_contract_test.reviews.json'
        try:
            path.write_text(json.dumps(record)+'\n',encoding='utf-8')
            comparison=client.get('/api/agentic/comparison?task_id=RW01V3').json()
            match=next(g for g in comparison['groups'] if g['model']=='mock/test:free')
            self.assertEqual(match['completed'],1)
            self.assertEqual(match['strict_passes'],1)
            info=client.get('/api/runs/'+filename).json()
            self.assertEqual(info['rows'][0]['score'],1.0)
            self.assertTrue(info['rows'][0]['grade_verified'])
            entry=client.get('/api/runs/'+filename+'/records/0').json()
            self.assertEqual(entry['audit']['grade']['strict_pass'],True)
            self.assertTrue(entry['audit']['prompt_sha_matches'])
            self.assertIsNone(entry['human_review'])
            reviewer={'status':'verified','reviewer':'Test reviewer',
                'notes':'Offline contract test: simulated source and tool observations checked.',
                'oracle_checked':True,'task_grader_alignment_checked':True,'evidence_support_checked':True}
            self.assertEqual(client.post('/api/runs/'+filename+'/records/0/review',json=reviewer).status_code,200)
            self.assertEqual(client.get('/api/runs/'+filename+'/records/0').json()['human_review']['status'],'verified')
            response=client.get('/api/runs/'+filename+'/bundle.zip')
            self.assertEqual(response.status_code,200)
            with ZipFile(io.BytesIO(response.content)) as z:
                members=set(z.namelist())
                self.assertIn('agent_graph.py',members)
                self.assertIn('benchmarks/grader.py',members)
                self.assertIn('benchmarks/runner.py',members)
                self.assertIn('benchmarks/environment.py',members)
                self.assertIn('tasks/RW01.json',members)
                self.assertIn('reference/RW01.json',members)
                self.assertIn('results/'+filename,members)
                self.assertNotIn('.env',members)
                self.assertNotIn('agentic_v3.py',members)
            bad=deepcopy(record)
            bad['grade']['score']=0
            path.write_text(json.dumps(bad)+'\n',encoding='utf-8')
            audited=client.get('/api/runs/'+filename+'/records/0').json()
            self.assertEqual(audited['audit']['stored_grade_matches'],False)
            self.assertEqual(audited['audit']['grade']['score'],1.0)
            self.assertIsNone(audited['human_review'])  # review hash-bound
        finally:
            path.unlink(missing_ok=True)
            review_path.unlink(missing_ok=True)

    def test_path_validation_and_empty_collection(self):
        for value in ('.env','../.env','something.log','_private.jsonl'):
            with self.assertRaises(Exception):
                file_path(value)
        for task_id in TASK_IDS:
            self.assertEqual(client.get('/api/agentic/comparison?task_id='+task_id).status_code,200)

if __name__=='__main__':
    unittest.main()
