"""Offline UI-provider authorization tests. Do not issue external API requests."""
from __future__ import annotations
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from api.main import app
from api.routes.experiment import LaunchRequest
from api.services.gemini_catalog import configured_models, allowed_model_ids

client = TestClient(app)
G = 'google-ai-studio/gemini-3.5-flash-lite'
O = 'nvidia/nemotron-3-ultra-550b-a55b:free'

class GoogleUIProviderTests(unittest.TestCase):
    def test_default_catalog_includes_hosted_gemma4(self):
        with patch('api.services.gemini_catalog.os.getenv', side_effect=lambda key, default=None: default if key == 'GEMINI_UI_MODELS' else ('dummy' if key == 'GOOGLE_API_KEY' else default)):
            ids = allowed_model_ids()
        self.assertIn('google-ai-studio/gemma-4-26b-a4b-it', ids)
        self.assertIn('google-ai-studio/gemma-4-31b-it', ids)
        self.assertNotIn('google-ai-studio/gemma-4-e4b-it', ids)

    def test_only_server_approved_google_ids(self):
        with patch.dict('os.environ', {'GEMINI_UI_MODELS':'gemini-3.5-flash-lite'}):
            self.assertIn(G, allowed_model_ids())
            self.assertEqual(LaunchRequest(models=[G], tasks=['RW01V4']).models, [G])
            with self.assertRaises(ValueError):
                LaunchRequest(models=['google-ai-studio/arbitrary-paid-model'], tasks=['RW01V4'])

    def test_key_never_returned(self):
        with patch.dict('os.environ', {'GOOGLE_API_KEY':'private-test-key','OPENROUTER_API_KEY':''}):
            response = client.get('/api/health')
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()['google_key_configured'])
            self.assertNotIn('private-test-key', response.text)

    def test_missing_google_key_prevents_launch(self):
        with patch.dict('os.environ', {'GOOGLE_API_KEY':'','GEMINI_API_KEY':'','OPENROUTER_API_KEY':''}):
            response = client.post('/api/experiment/start', json={'models':[G], 'tasks':['RW01V4'], 'confirm':True})
            self.assertEqual(response.status_code, 400)
            self.assertIn('GOOGLE_API_KEY',response.text)

    def test_mixed_providers_launch_dispatch(self):
        from unittest.mock import MagicMock
        with patch.dict('os.environ', {'GOOGLE_API_KEY':'dummy','OPENROUTER_API_KEY':'dummy'}), \
             patch('api.routes.experiment.valid_models', return_value=[{'id':O}]), \
             patch('api.routes.experiment.subprocess.Popen') as popen, \
             patch('api.routes.experiment.start_log_tee'):
            proc = MagicMock()
            proc.poll.return_value = 0
            popen.return_value = proc
            response = client.post('/api/experiment/start', json={
                'models':[G,O], 'tasks':['RW01V4'], 'confirm':True})
            self.assertEqual(response.status_code,202, response.text)
            command = popen.call_args.args[0]
            self.assertIn('run_mixed_providers.py', ' '.join(command))
            self.assertIn(G, command)
            self.assertIn(O, command)
            self.assertEqual(response.json()['requests_planned'],96)

    def test_google_multi_model_allowed(self):
        with patch.dict('os.environ', {'GEMINI_UI_MODELS':'gemini-3.5-flash-lite,gemma-4-31b-it'}):
            self.assertEqual(len(LaunchRequest(models=[G,'google-ai-studio/gemma-4-31b-it'], tasks=['RW01V4']).models),2)

    def test_google_catalog_when_openrouter_down(self):
        with patch('api.services.model_cache.fetch_free_models',side_effect=RuntimeError('offline')):
            from api.services import model_cache
            with patch.dict(model_cache.model_cache, {'at':0.0,'models':[]}):
                response = client.get('/api/models?refresh=true')
            self.assertEqual(response.status_code,200)
            self.assertIn(G,[x['id'] for x in response.json()])

if __name__ == '__main__': unittest.main()
