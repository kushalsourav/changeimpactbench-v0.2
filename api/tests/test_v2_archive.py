"""Historical v1 records remain immutable and excluded from prospective v2 statistics."""
from __future__ import annotations
import json
from pathlib import Path
import unittest
from fastapi.testclient import TestClient
from api.main import app
from tasks import ROOT

client = TestClient(app)

class ArchiveTests(unittest.TestCase):
    def test_v1_stored_grade_preserved_not_regraded_or_pooled(self):
        path = ROOT / 'results' / 'ui_historical_v1_preservation_test.jsonl'
        original = {'task_id': 'RW01',
            'benchmark_version': 'publicincident-rw01-v1-langgraph-v1',
            'agent_framework': 'langchain-create-agent/langgraph-checkpointed',
            'model_requested': 'nvidia/example:free', 'trial': 1,
            'status': 'completed',
            'final_diagnosis': {'root_cause': 'a free-text causal explanation'},
            'grade': {'score': .75, 'root_correct': False, 'strict_pass': False}}
        raw = json.dumps(original) + '\n'
        try:
            path.write_text(raw, encoding='utf-8')
            self.assertNotIn(path.name, [r['name'] for r in client.get('/api/runs').json()])
            self.assertEqual(client.get('/api/runs/' + path.name).status_code, 404)
            self.assertIn(path.name, [r['filename'] for r in client.get('/api/archive/runs').json()])
            archived = client.get('/api/archive/runs/' + path.name)
            self.assertEqual(archived.status_code, 200)
            self.assertEqual(archived.json()['records'][0]['stored_grade']['score'], .75)
            self.assertEqual(archived.json()['verification_status'],
                             'not independently replayed under current v3 source')
            self.assertEqual(client.get('/api/archive/runs/' + path.name + '/raw.jsonl').text, raw)
            self.assertEqual(path.read_text(encoding='utf-8'), raw)
            groups = client.get('/api/agentic/comparison', params={'task_id':'RW01V3'}).json()['groups']
            self.assertFalse(any(g['model'] == 'nvidia/example:free' for g in groups))
        finally:
            path.unlink(missing_ok=True)

    def test_v2_orchestration_error_is_archived_unchanged(self):
        path=ROOT / 'results' / 'ui_historical_v2_preservation_test.jsonl'
        original={'task_id':'RW01V2','benchmark_version':'publicincident-rw01-v2-langgraph-v1',
                  'agent_framework':'langchain-create-agent/langgraph-checkpointed',
                  'model_requested':'nvidia/example:free','trial':1,'status':'api_error',
                  'error':'GraphRecursionError', 'grade':None}
        raw=json.dumps(original)+'\n'
        try:
            path.write_text(raw,encoding='utf-8')
            self.assertEqual(client.get('/api/runs/'+path.name).status_code,404)
            response=client.get('/api/archive/runs/'+path.name)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['records'][0]['status'],'api_error')
            self.assertEqual(client.get('/api/archive/runs/'+path.name+'/raw.jsonl').text,raw)
            self.assertEqual(path.read_text(encoding='utf-8'),raw)
        finally:
            path.unlink(missing_ok=True)

if __name__=='__main__':
    unittest.main()
