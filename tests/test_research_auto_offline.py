"""Research mode is separately opted in, never a grading authority."""
from __future__ import annotations
import os
import unittest
from unittest.mock import patch
from tools import auto_synthesis
from api.routes.synthesis import SynthesisRequest
from api.routes import synthesis
from fastapi import HTTPException

class ResearchAutoOfflineTests(unittest.TestCase):
    def test_google_model_validation_is_restricted_to_research(self):
        with patch.dict(os.environ, {'GOOGLE_API_KEY':'fake-offline-key'}):
            with self.assertRaises(HTTPException) as raised:
                synthesis.generate_synthesis('ui_nonexistent.jsonl',SynthesisRequest(model='recursive/flint-v1.0:free',confirm=True))
            self.assertEqual(raised.exception.status_code,400)
    def test_research_mode_requires_separate_confirmation(self):
        with self.assertRaises(HTTPException) as raised:
            synthesis.generate_synthesis('ui_nonexistent.jsonl',SynthesisRequest(model='google-ai-studio/gemini-3.5-flash-lite',confirm=False))
        self.assertEqual(raised.exception.status_code,400)
    def test_auto_mode_noop_without_env_toggle(self):
        with patch.dict(os.environ, {'CIB_AUTO_GEMINI_RESEARCH':'0'}), patch('sys.argv',['auto_synthesis.py','--run','ui_fake.jsonl']):
            self.assertEqual(auto_synthesis.main(),0)

if __name__=='__main__':unittest.main()
