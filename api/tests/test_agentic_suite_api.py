"""API-facing offline tests for AG09-AG12; no live provider credentials."""
import json
import unittest
from fastapi.testclient import TestClient
from api import main as server
from tasks import ROOT
from tests.test_agentic_suite import fake_episode

client = TestClient(server.app)

class AgenticSuiteApiTests(unittest.TestCase):
    def test_catalog_task_detail_and_schema(self):
        catalog = client.get('/api/tasks').json()
        for task_id in ('AG08V4','AG09','AG10','AG11','AG12'):
            match = next(t for t in catalog if t['id'] == task_id)
            self.assertEqual(match['condition'],'agentic')
            detail = client.get(f'/api/tasks/{task_id}').json()
            self.assertEqual(detail['case']['id'],task_id)
            self.assertFalse(detail['reference_visible_to_agent'])
            self.assertEqual(detail['reference']['fix_id'],next(
                action['id'] for action in detail['case']['actions']
                if action['id']==detail['reference']['fix_id']))
            self.assertEqual(client.get('/api/agentic/comparison',params={'task_id':task_id}).status_code,200)

    def test_unsupported_mixed_task_versions_rejected(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            server.LaunchRequest(models=['mock/suite:free'], tasks=['AG09','AG10'],condition='agentic')

    def test_saved_suite_records_replay_and_export_correct_source(self):
        name='ui_suite_offline_test.jsonl'
        p=ROOT/'results'/name
        try:
            p.write_text(json.dumps(fake_episode('AG09'))+'\n',encoding='utf-8')
            run=client.get(f'/api/runs/{name}')
            self.assertEqual(run.status_code,200)
            self.assertEqual(run.json()['rows'][0]['pass'],True)
            detail=client.get(f'/api/runs/{name}/records/0').json()
            self.assertEqual(detail['audit']['prompt_sha_matches'],True)
            self.assertEqual(detail['audit']['stored_grade_matches'],True)
            self.assertEqual(detail['audit']['reference_matches'],True)
            import io,zipfile
            data=client.get(f'/api/runs/{name}/bundle.zip').content
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names=z.namelist()
                self.assertIn('tasks/T09.json', names)
                self.assertIn('reference/T09.json',names)
                self.assertIn('agentic_suite.py',names)
                self.assertIn('run_agentic_suite.py',names)
        finally:
            p.unlink(missing_ok=True)

if __name__ == '__main__': unittest.main()
