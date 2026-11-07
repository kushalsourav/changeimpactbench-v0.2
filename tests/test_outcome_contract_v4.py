"""Deterministic V4 verdicts; these are offline scripted trajectories, NOT model trials."""
from __future__ import annotations
import json
import unittest
from benchmarks.native_agent import GraphEnvironment, agent_prompt
from benchmarks.grader import replay_record
from benchmarks.spec import reference_trajectory
from benchmarks.runner import run_episode
from tests_fake_graph_v4 import scripted_factory

class OutcomeV4Tests(unittest.TestCase):
    def test_reference_passes_each_v4_case(self):
        for task in ('RW01V4','RW02V4','RW03V4'):
            with self.subTest(task=task):
                record=run_episode(task,'mock/v4:free',1,'offline-test-token',1024,'low',0,3,
                                   graph_factory=scripted_factory)
                self.assertEqual(record['status'],'completed')
                self.assertTrue(record['replay_verified'])
                self.assertTrue(record['grade']['strict_pass'])
                self.assertEqual(record['grade']['pass_contract'],'outcome-v4')

    def test_rejected_premature_simulation_reported_but_not_outcome_failure(self):
        record=run_episode('RW01V4','mock/v4:free',1,'offline-test-token',1024,'low',0,3,
                           graph_factory=lambda env,*_: scripted_factory(env,premature=True))
        self.assertTrue(record['replay_verified'])
        grade=record['grade']
        self.assertTrue(grade['strict_pass'])
        self.assertEqual(grade['score'],.95)
        self.assertEqual(grade['procedure_score'],5)
        self.assertEqual(grade['protocol_errors'][0]['reason'],
                         'Call prepare_repair with an evidence-backed plan before simulation')
        self.assertEqual(grade['strict_failure_reasons'],[])

    def test_invalid_repair_remains_a_strict_failure(self):
        record=run_episode('RW01V4','mock/v4:free',1,'offline-test-token',1024,'low',0,3,
                           graph_factory=lambda env,*_: scripted_factory(env,wrong_fix=True))
        self.assertTrue(record['replay_verified'])
        self.assertFalse(record['grade']['strict_pass'])
        self.assertFalse(record['grade']['recovery_success'])

    def test_v4_metrics_do_not_announce_direct_fault(self):
        env=GraphEnvironment('RW01V4')
        x=json.loads(env.execute('inspect_metrics',{'service':'mysql-east'},'1'))
        self.assertNotIn('is_direct_local_fault',x['result'])
        y=json.loads(env.execute('inspect_logs',{'service':'mysql-east'},'2'))
        self.assertNotIn('inspect the relevant configuration',str(y))
        historical=GraphEnvironment('RW01V3')
        z=json.loads(historical.execute('inspect_metrics',{'service':'mysql-east'},'1'))
        self.assertTrue(z['result']['is_direct_local_fault'])

    def test_v3_prompt_and_handoff_remain_explicit(self):
        prompt=json.loads(agent_prompt('RW01V3'))
        self.assertTrue(any('Only after prepare_repair' in x for x in prompt['rules']))
        self.assertNotIn('evaluation_contract',prompt)
        self.assertIn('evaluation_contract',json.loads(agent_prompt('RW01V4')))
