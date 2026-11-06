"""Offline release integrity tests; no network, no real provider outcomes."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from tools.audit_benchmark import run_audit, _semantic_flags
from tools.make_submission import source_members, KEY_PATTERN, ASSIGN_PATTERN


class ReleaseToolsTests(unittest.TestCase):
    def test_oracle_reference_audit_does_not_report_mocked_live_model_results(self):
        report = run_audit()
        self.assertEqual(report['counts']['seed_cases'], 12)
        self.assertEqual(report['counts']['seed_checks_pass'], 12)
        self.assertEqual(report['counts']['new_agentic_reference_checks_pass'], 5)
        self.assertTrue(all(x.get('human_review') == 'pending' for x in report['agentic_tasks'] if x['task'] != 'AG08V3'))

    def test_semantic_flags_are_warnings_not_automatic_score_changes(self):
        record = {'final_diagnosis': {
            'rationale': 'issuer_epoch=8 > trusted_through_epoch=8',
            'evidence_ids': ['EV002','EV003']
        }, 'trajectory': [
            {'tool':'apply_repair','provider_turn':1,'observation':{'event_id':'EV001'}},
            {'tool':'inspect_config','provider_turn':2,'observation':{'event_id':'EV002'}},
            {'tool':'read_alert','provider_turn':3,'observation':{'event_id':'EV003'}},
        ]}
        flags = _semantic_flags(record)
        self.assertEqual(len(flags), 2)
        self.assertTrue(any('False arithmetic' in value for value in flags))
        self.assertTrue(any('Post-repair' in value for value in flags))
        self.assertNotIn('grade', record)

    def test_submission_manifest_never_includes_env_or_generated_web_dependencies(self):
        paths=[p.relative_to(Path(__file__).resolve().parent.parent).as_posix() for p in source_members()]
        self.assertIn('web/package-lock.json', paths)
        self.assertIn('agentic_suite.py', paths)
        self.assertNotIn('.env', paths)
        self.assertFalse(any('node_modules' in p or '.next' in p or '__pycache__' in p for p in paths))
        self.assertIsNone(KEY_PATTERN.search(b'OPENROUTER_API_KEY=YOUR_PRIVATE_OPENROUTER_KEY'))
        self.assertIsNotNone(ASSIGN_PATTERN.search(b'export OPENROUTER_API_KEY="paste-your-key-locally"'))


if __name__=='__main__':
    unittest.main()
