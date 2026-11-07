"""Old files must not appear in the clean-start UI or resolve by orphaned link."""
import json
import unittest
from fastapi.testclient import TestClient
from api.main import app
from tasks import ROOT

client = TestClient(app)

class VisibleNativeRunsTest(unittest.TestCase):
    def test_legacy_jsonl_is_not_displayed_or_replayed(self):
        filename = 'ui_architecture_legacy_contract.jsonl'
        path = ROOT / 'results' / filename
        try:
            path.write_text(json.dumps({
                'task_id': 'AG12', 'benchmark_version': 'agentic-ag12-v1',
                'model_requested': 'nvidia/legacy:free', 'trial': 1,
                'status': 'budget_exhausted',
            }) + '\n', encoding='utf-8')
            names = [r['name'] for r in client.get('/api/runs').json()]
            self.assertNotIn(filename, names)
            self.assertEqual(client.get('/api/runs/' + filename).status_code, 404)
            self.assertEqual(client.get('/api/runs/' + filename + '/records/0').status_code, 404)
            self.assertEqual(client.get('/api/runs/' + filename + '/raw.jsonl').status_code, 404)
            for task in ('RW01V3','RW02V3','RW03V3'):
                result=client.get('/api/agentic/comparison',params={'task_id':task})
                self.assertEqual(result.status_code,200)
                self.assertFalse(any(group['model']=='nvidia/legacy:free' for group in result.json()['groups']))
        finally:
            path.unlink(missing_ok=True)

    def test_modular_api_and_stream_route_are_registered(self):
        assert client.get('/api/health').json()['version'] == '0.9.21'
        paths = set(app.openapi()['paths'])
        self.assertIn('/api/experiment/log/stream', paths)
        self.assertIn('/api/tasks/{task_id}', paths)
        self.assertIn('/api/runs/{filename}/bundle.zip', paths)
        self.assertIn('/api/runs/{filename}/records/{index}/review', paths)

if __name__ == '__main__': unittest.main()
