"""Read-only V6CF-only public API checks; no provider calls made."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from unittest.mock import patch
from api.main import app
from api.routes.experiment import LaunchRequest


class V6APIReadOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_task_catalog_and_original_names(self):
        r=self.client.get('/api/tasks')
        self.assertEqual(r.status_code,200)
        tasks=r.json()
        self.assertEqual([t['id'] for t in tasks], [f'RW{i:02}V6CF' for i in range(1,7)])
        for task in tasks:
            self.assertIn('original_source_name', task)
            self.assertTrue(task['source_url'].startswith('https://'))
            self.assertIn('synthetic', task['dataset_origin'])
            self.assertEqual(task['dataset_name'], task['original_source_name'])

    def test_detail_reference_is_review_only(self):
        r=self.client.get('/api/tasks/RW01V6CF')
        self.assertEqual(r.status_code,200)
        data=r.json()
        self.assertFalse(data['reference_visible_to_agent'])
        self.assertNotIn('GitHub', data['prompt'])
        self.assertIn('reference', data)
        self.assertEqual(sorted(data['service_codes'].values()), [f'svc-{i:03d}' for i in range(1,15)])

    def test_retired_task_cannot_launch_or_be_accessed(self):
        for task_id in ('RW01V4','RW01V5','RW01V6N'):
            self.assertEqual(self.client.get('/api/tasks/'+task_id).status_code,404)
            with self.assertRaises(ValidationError):
                LaunchRequest(models=['nvidia/mock:free'],tasks=[task_id])
        self.assertEqual(self.client.get('/api/agentic/comparison?task_id=RW01V4').status_code,400)
        self.assertEqual(self.client.get('/api/agentic/comparison?task_id=RW01V6CF').status_code,200)

    def test_input_token_limit_validated_with_launch_request(self):
        request = LaunchRequest(models=['nvidia/mock:free'], tasks=['RW01V6CF'],
                                max_input_tokens=75000)
        self.assertEqual(request.max_input_tokens, 75000)
        self.assertEqual(LaunchRequest(models=['nvidia/mock:free'], tasks=['RW01V6CF'],
                                       max_input_tokens=10_000_000).max_input_tokens, 10_000_000)
        for value in (4095, 10_000_001):
            with self.assertRaises(ValidationError):
                LaunchRequest(models=['nvidia/mock:free'], tasks=['RW01V6CF'],
                              max_input_tokens=value)

    def test_output_token_ceiling_20k_without_starting_provider(self):
        req = LaunchRequest(models=['nvidia/mock:free'], tasks=['RW01V6CF'],
                            max_tokens=20_000, max_input_tokens=10_000_000)
        self.assertEqual(req.max_tokens, 20_000)
        self.assertEqual(req.max_input_tokens, 10_000_000)
        for value in (511, 20_001):
            with self.assertRaises(ValidationError):
                LaunchRequest(models=['nvidia/mock:free'], tasks=['RW01V6CF'],
                              max_tokens=value)

    def test_valid_launch_not_executed_without_approval(self):
        record=LaunchRequest(models=['nvidia/mock:free'],tasks=['RW02V6CF'],confirm=False)
        r=self.client.post('/api/experiment/start',json=record.model_dump())
        self.assertEqual(r.status_code,400)

    def test_finished_run_status_is_restored_from_results_folder(self):
        from api.services import process_manager
        with TemporaryDirectory() as folder:
            root = Path(folder)
            output = root / 'ui_saved.jsonl'
            output.write_text(json.dumps({
                'model_requested': 'anthropic/example', 'task_id': 'RW02V6CF', 'trial': 1,
            }) + '\n', encoding='utf-8')
            (root / 'ui_saved.log').write_text(
                '    turn=1/48 · Anthropic request ...\n    turn=1/48 · Anthropic completed\n',
                encoding='utf-8',
            )
            manifest = {
                'experiment_id': 'saved', 'output_file': output.name,
                'models': ['anthropic/example'], 'tasks': ['RW02V6CF'], 'trials': 1,
                'requests_planned': 48, 'created_utc': '2026-01-01T00:00:00+00:00',
            }
            with patch.object(process_manager, 'RESULTS', root), \
                 patch.object(process_manager, 'visible_runs', return_value=[output]), \
                 patch.object(process_manager, 'run_manifest', return_value=manifest):
                state = process_manager._restored_process_state()
        self.assertEqual(state['status'], 'finished')
        self.assertEqual(state['output_file'], output.name)
        self.assertEqual(state['records_saved'], 1)
        self.assertTrue(state['restored_from_disk'])

if __name__=='__main__':
    unittest.main()
