"""Offline chart aggregation contract tests for v0.9. No network / provider calls."""
import json
import unittest

from fastapi.testclient import TestClient
from api import main as server
from api.tests.test_research_v08 import offline_episode
from agentic_v3 import reference_trajectory
from tasks import ROOT

client = TestClient(server.app)


class ResearchStoryV09Tests(unittest.TestCase):
    def test_comparison_distinguishes_safe_recovery_from_initial_inventory_errors(self):
        complete = offline_episode(reference_trajectory(), 'v09-complete')
        assert complete['status'] == 'completed'
        assert complete['grade']['strict_pass'] is True
        # A fully restorative safe episode with a mistaken initial outage inventory.
        altered = []
        for tool, args in reference_trajectory():
            args = dict(args)
            if tool == 'submit_diagnosis':
                changed = [s for s in args['failed_services'] if s != 'audit-west']
                changed.append('front-door')
                args['failed_services'] = changed
            altered.append((tool, args))
        impact_error = offline_episode(altered, 'v09-blast-radius')
        assert impact_error['grade']['strict_pass'] is False
        assert impact_error['grade']['recovery_success'] is True
        assert impact_error['grade']['root_correct'] is True
        target = ROOT / 'results'
        filenames = ['ui_v09_complete.jsonl', 'ui_v09_impact.jsonl']
        try:
            for name, data in zip(filenames, (complete, impact_error)):
                (target / name).write_text(json.dumps(data) + '\n', encoding='utf-8')
            groups = client.get('/api/agentic/comparison', params={'task_id': 'AG08V3'}).json()['groups']
            matching = [g for g in groups if g['model'] == 'mock/test:free']
            self.assertEqual(len(matching), 1)
            grp = matching[0]
            self.assertEqual(grp['episodes'], 2)
            self.assertEqual(grp['completed'], 2)
            self.assertEqual(grp['strict_passes'], 1)
            self.assertEqual(grp['complete_safe_repairs'], 2)
            self.assertEqual(grp['initial_impact_errors'], 1)
            self.assertEqual(grp['root_cause_errors'], 0)
            self.assertEqual(grp['repair_selection_errors'], 0)
            self.assertEqual(grp['protocol_error_episodes'], 0)
            self.assertEqual(grp['strict_pass_rate_completed'], .5)
        finally:
            for name in filenames:
                (target / name).unlink(missing_ok=True)

    def test_version_rejection_remains(self):
        self.assertEqual(client.get('/api/agentic/comparison', params={'task_id':'T08'}).status_code,400)
