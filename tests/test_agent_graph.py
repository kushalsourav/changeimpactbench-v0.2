"""Offline native-tool collector/replay tests; NO fabricated provider outcomes.

These tests inject a fake graph object to validate the native tool/event format.
They DO NOT demonstrate that third-party LangChain or OpenRouter succeeded.
"""
from __future__ import annotations
from benchmarks.grader import replay_record as _legacy_replay

from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from agent_graph import (ENGINE, GRAPH_BASE, GraphEnvironment,
                         MAX_MODEL_CALLS, TASK_IDS, VERSIONS,
                         agent_prompt, replay_record, source_case)
from benchmarks.spec import reference_trajectory, REGISTRY
from run_graph_agent import run_episode


class Message(SimpleNamespace):
    pass


class FakeReferenceGraph:
    def __init__(self, env: GraphEnvironment, committed: str | None = None):
        self.env = env
        self.committed = committed

    def stream(self, _input, config, stream_mode):
        assert stream_mode == 'updates'
        trajectory = reference_trajectory(self.env.task_id)
        if self.committed:
            # Offline counterexample uses the same public interface, no real LLM.
            trajectory = [(name, {'action_id': self.committed} if name in ('simulate_repair','apply_repair') and args.get('action_id') == 'A03' else
                           {**args, 'fix_id': self.committed} if name == 'submit_diagnosis' else args)
                          for name,args in trajectory]
        for n, (name, args) in enumerate(trajectory, 1):
            identifier = f'fake-provider-{n}'
            yield {'model': {'messages': [Message(
                type='ai', content='',
                tool_calls=[{'name': name, 'args': args, 'id': identifier}],
                usage_metadata={'input_tokens': 100, 'output_tokens': 30},
                response_metadata={'model_name': 'mock/reference:free', 'finish_reason': 'tool_calls'},
                additional_kwargs={}, id=identifier,
            )]}}
            obs = self.env.execute(name, args, identifier)
            yield {'tools': {'messages': [Message(type='tool', content=obs)]}}


def fake_factory(env, *_args):
    return FakeReferenceGraph(env)


class GraphBenchmarkTests(unittest.TestCase):
    def test_names_distinct_and_historical_sources_untouched(self):
        self.assertEqual({t for t in TASK_IDS if t.endswith('V4')}, {'RW01V4','RW02V4','RW03V4','RW04V4','RW05V4','RW06V4'})
        self.assertNotIn('reference', agent_prompt('RW03V3').lower())
        # The seed/source document is reviewer-only, NOT in agent prompt.
        for task in REGISTRY:
            self.assertEqual(VERSIONS[task], REGISTRY[task].version)
            self.assertGreaterEqual(len(source_case(task)['facts']['topology']), 10)
            self.assertTrue(REGISTRY[task].source_url.startswith('https://'))
            self.assertNotIn('"facts"', agent_prompt(task))
            self.assertNotIn('"fix_id"', agent_prompt(task))

    def test_initial_health_scan_is_not_an_oracle_of_causes(self):
        env = GraphEnvironment('RW03V3')
        result = json.loads(env.execute('scan_service_health', {}, 'scan-1'))
        self.assertEqual(result['result']['snapshot'], 'initial')
        self.assertEqual(result['result']['service_count'], 10)
        self.assertEqual(len(result['result']['statuses']), 10)
        self.assertNotIn('root_cause', result['result'])
        self.assertNotIn('fix_id', result['result'])
        self.assertEqual(len(env.steps), 1)
        self.assertEqual(result['event_id'], 'EV001')
        self.assertEqual(json.loads(env.execute('scan_service_health', {'unexpected':True}, 'bad'))['rejected'],True)
        self.assertEqual(len(env.steps), 1)

    def test_all_public_reference_trajectories_grade_with_independent_replay(self):
        for name in sorted(TASK_IDS):
            with self.subTest(name=name):
                record = run_episode(name, 'mock/reference:free', 1, 'not-a-real-key',
                                     2048, 'low', 0, 3, graph_factory=fake_factory)
                self.assertEqual(record['agent_framework'], ENGINE)
                self.assertEqual(record['status'], 'completed')
                self.assertTrue(record['replay_verified'])
                self.assertTrue(_legacy_replay(record)['grade']['strict_pass'])
                self.assertTrue(_legacy_replay(record)['grade']['recovery_success'])
                self.assertEqual(record['committed_effect']['unavailable_after'], [])
                self.assertLess(record['provider_requests'], MAX_MODEL_CALLS)
                self.assertEqual(record['provider_requests'], len(record['turns']))
                self.assertTrue(any(t['tool'] == 'scan_service_health' for t in record['trajectory']))
                self.assertNotIn('not-a-real-key', json.dumps(record))

    def test_tampered_native_tool_arguments_or_observation_not_verified(self):
        record = run_episode('RW01V3', 'mock/reference:free', 1, 'token', 1024,
                             'low', 0, 3, graph_factory=fake_factory)
        self.assertTrue(_legacy_replay(record)['grade']['strict_pass'])
        bad = deepcopy(record)
        bad['turns'][1]['tool_calls'][0]['name'] = 'inspect_metrics'
        self.assertFalse(_legacy_replay(bad)['verified'])
        bad = deepcopy(record)
        bad['trajectory'][1]['observation']['result']['statuses']['status-page'] = 'unavailable'
        self.assertFalse(_legacy_replay(bad)['verified'])
        bad = deepcopy(record)
        bad['source_hashes']['oracle.py'] = 'tampered'
        self.assertFalse(_legacy_replay(bad)['verified'])
        bad = deepcopy(record)
        bad['grade']['score'] = 0
        replay = _legacy_replay(bad)
        self.assertTrue(replay['verified'])
        self.assertEqual(replay['grade']['score'], _legacy_replay(record)['grade']['score'])

    def test_strict_rejects_partial_unsafe_and_expensive_complete_repairs(self):
        # AG08: A02 is partial-safe, A04 causes fresh outages, A05 is safe
        # complete but unnecessarily expensive. None may pass strict grading.
        for action in ('A01','A02','A04'):
            with self.subTest(action=action):
                rec = run_episode('RW01V3','mock/negative:free',1,'token',1024,'low',0,3,
                        graph_factory=lambda env,*_:FakeReferenceGraph(env, action))
                self.assertEqual(rec['status'],'completed')
                self.assertTrue(rec['replay_verified'])
                self.assertFalse(_legacy_replay(rec)['grade']['strict_pass'])
                self.assertFalse(_legacy_replay(rec)['grade']['fix_correct'])
                if action=='A04':
                    self.assertTrue(_legacy_replay(rec)['grade']['recovery_success'])
                    self.assertTrue(_legacy_replay(rec)['grade']['recovery_safe'])
                if action=='A01':
                    self.assertFalse(_legacy_replay(rec)['grade']['recovery_success'])
                if action=='A02':
                    self.assertFalse(_legacy_replay(rec)['grade']['recovery_success'])

    def test_budget_only_episode_is_non_gradeable(self):
        class FakeBudgetGraph:
            def __init__(self, env): self.env=env
            def stream(self, _input, config, stream_mode):
                for i in range(MAX_MODEL_CALLS):
                    name, args = 'inspect_metrics', {'service':'mysql-east'}
                    identifier = f'budget-{i}'
                    yield {'model': {'messages': [Message(
                        type='ai', content='', tool_calls=[{'name':name,'args':args,'id':identifier}],
                        usage_metadata={},response_metadata={},additional_kwargs={},id=identifier
                    )]}}
                    obs = self.env.execute(name, args, identifier)
                    yield {'tools':{'messages':[Message(type='tool',content=obs)]}}
        record = run_episode('RW03V3','mock/budget:free',1,'token',1024,'low',0,3,
                             graph_factory=lambda env,*_:FakeBudgetGraph(env))
        self.assertEqual(record['status'],'budget_exhausted')
        self.assertTrue(record['replay_verified'])
        self.assertNotIn('grade',record)
        self.assertIsNone(_legacy_replay(record)['grade'])
        self.assertEqual(record['provider_requests'],48)

if __name__ == '__main__':
    unittest.main()
