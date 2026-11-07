"""Offline validation of direct Anthropic catalog and mixed-provider dispatch."""
import os
import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from api.main import app
from api.routes.experiment import LaunchRequest
from api.services.anthropic_catalog import allowed_model_ids
from tools.run_mixed_providers import commands

A = 'anthropic/claude-sonnet-5-5'
O = 'nvidia/nemotron-3-ultra-550b-a55b:free'
G = 'google-ai-studio/gemini-3.5-flash-lite'
client = TestClient(app)

class AnthropicProviderTests(unittest.TestCase):
    def test_whitelisted_and_multiselectable(self):
        self.assertIn(A, allowed_model_ids())
        self.assertEqual(LaunchRequest(models=[A,O,G], tasks=['RW05V4']).models, [A,O,G])
        with self.assertRaises(ValueError):
            LaunchRequest(models=['anthropic/unknown-claude'], tasks=['RW05V4'])

    def test_catalog_without_openrouter(self):
        with patch('api.services.model_cache.fetch_free_models', side_effect=RuntimeError('offline')):
            response = client.get('/api/models?refresh=true')
        self.assertEqual(response.status_code, 200)
        self.assertIn(A, [item['id'] for item in response.json()])

    def test_health_does_not_disclose_key(self):
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY':'secret-only-for-test','OPENROUTER_API_KEY':''}):
            response = client.get('/api/health')
        self.assertTrue(response.json()['anthropic_key_configured'])
        self.assertNotIn('secret-only-for-test', response.text)

    def test_missing_key_blocks_paid_provider(self):
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY':''}):
            response = client.post('/api/experiment/start', json={'models':[A],'tasks':['RW05V4'],'confirm':True})
        self.assertEqual(response.status_code, 400)
        self.assertIn('ANTHROPIC_API_KEY', response.text)

    def test_direct_and_openrouter_mixed_launch(self):
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY':'fake','OPENROUTER_API_KEY':'fake'}), \
             patch('api.routes.experiment.valid_models', return_value=[{'id':O}]), \
             patch('api.routes.experiment.subprocess.Popen') as popen, \
             patch('api.routes.experiment.start_log_tee'):
            proc = MagicMock()
            proc.poll.return_value = 0
            popen.return_value = proc
            response = client.post('/api/experiment/start', json={'models':[A,O], 'tasks':['RW05V4'],'trials':1,'confirm':True})
        self.assertEqual(response.status_code,202,response.text)
        self.assertIn('run_mixed_providers.py', ' '.join(popen.call_args.args[0]))
        self.assertEqual(response.json()['requests_planned'],96)

    def test_versioned_tasks_reach_direct_provider_runners(self):
        """Validate CLI task choices without API keys or external calls."""
        import subprocess
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        for adapter in ('run_anthropic.py', 'run_gemini.py'):
            help_result = subprocess.run(
                [sys.executable, str(root / 'tools' / adapter), '--help'],
                cwd=root, capture_output=True, text=True, check=False,
            )
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            for valid in ('RW01V4', 'RW05V5', 'RW03V6N', 'RW04V6CF'):
                self.assertIn(valid, help_result.stdout, (adapter, valid))
            self.assertNotIn('RW99V6CF', help_result.stdout)

    def test_anthropic_v6_counterfactual_dispatch(self):
        task = 'RW04V6CF'
        self.assertEqual(LaunchRequest(models=[A], tasks=[task]).tasks, [task])
        cmd = next(commands([A], task, 1, 4, 0, 8000, 'low',
                            ['results/anthropic_v6_test.jsonl']))
        self.assertIn('run_anthropic.py', ' '.join(cmd))
        self.assertEqual(cmd[cmd.index('--task') + 1], task)

    def test_runner_routes_exact_models(self):
        result = list(commands([A,O,G], 'RW05V4', 1, 4, 0, 8000, 'low',
                               ['results/a.jsonl','results/b.jsonl','results/c.jsonl']))
        self.assertIn('run_anthropic.py', ' '.join(result[0]))
        self.assertIn('run_graph_agent.py', ' '.join(result[1]))
        self.assertIn('run_gemini.py', ' '.join(result[2]))

if __name__ == '__main__': unittest.main()
