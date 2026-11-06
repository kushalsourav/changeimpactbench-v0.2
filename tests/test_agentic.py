"""Agentic AG08 safety, isolation, replay integrity, and fake-provider end-to-end tests.

Absolutely no OpenRouter/network requests occur in these tests.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import unittest

from agentic import (AgentEnvironment, MAX_SIMULATIONS, MAX_TOOL_CALLS, TASK_ID,
                     VERSION, ProtocolError, agent_prompt, digest, implementation_hashes, parse_tool_call,
                     reference_trajectory, replay_record, source_case)
from oracle import reference_answer, simulate
from run_agentic import run_episode, EpisodeInterrupted


def offline_record(actions=None, status='completed'):
    env = AgentEnvironment()
    for tool, args in actions if actions is not None else reference_trajectory():
        observation = env.execute(tool, args)
        env.steps[-1]['raw_model_output'] = json.dumps({'tool': tool, 'arguments': args})
        env.steps[-1]['provider_turn'] = len(env.steps)
    return {'task_id': TASK_ID, 'benchmark_version': VERSION,
            'prompt_sha256': sha256(agent_prompt().encode()).hexdigest(),
            'case_sha256': digest(source_case()), 'source_hashes': implementation_hashes(),
            'status': status,
            'trajectory': env.steps, 'committed_effect': env.committed_effect,
            'final_diagnosis': env.final, 'raw_output': env.steps[-1]['raw_model_output'] if env.steps else ''}


class AgenticEnvironmentTests(unittest.TestCase):
    def test_agent_prompt_does_not_contain_golden_keys_or_oracle_answer(self):
        prompt = agent_prompt()
        self.assertNotIn('"root_cause": "H04"', prompt)
        self.assertNotIn('"fix_id": "A03"', prompt)
        self.assertNotIn('\"failed_services\": [\n    \"api-north\"', prompt)
        self.assertNotIn('"facts"', prompt)
        self.assertIn('inspect_config', prompt)

    def test_reference_agent_passes_and_is_replayed(self):
        rec = offline_record()
        check = replay_record(rec)
        self.assertTrue(check['verified'])
        self.assertTrue(check['grade']['strict_pass'])
        self.assertEqual(check['grade']['score'], 1)
        self.assertFalse(check['grade']['unsafe_commit'])
        self.assertEqual(check['grade']['simulation_calls'], 2)

    def test_simulation_is_counterfactual_and_never_mutates_real_state(self):
        env = AgentEnvironment()
        before = deepcopy(env.facts)
        env.execute('simulate_repair', {'action_id':'A04'})
        self.assertEqual(env.facts, before)
        env.execute('simulate_repair', {'action_id':'A03'})
        self.assertEqual(env.facts, before)
        self.assertIsNone(env.committed)

    def test_cheap_repair_causes_new_outages(self):
        env = AgentEnvironment()
        result = env.execute('apply_repair', {'action_id':'A04'})
        self.assertGreater(result['result']['newly_unavailable_count'], 0)
        self.assertIn('unsafe_committed_repair', env.violations)
        self.assertTrue(env.committed_effect['newly_unavailable'])

    def test_unsafe_commit_is_strict_failure_even_with_correct_diagnosis(self):
        ref = reference_answer(source_case())
        actions = [('read_alert', {}), ('list_repairs', {}),
                   ('simulate_repair', {'action_id':'A04'}),
                   ('apply_repair', {'action_id':'A04'}),
                   ('submit_diagnosis', {**ref, 'fix_id':'A04', 'evidence_ids':['EV001','EV003'],
                                         'rationale':'Incorrectly chose cheaper repair'})]
        grade = replay_record(offline_record(actions))['grade']
        self.assertFalse(grade['pass'])
        self.assertTrue(grade['unsafe_commit'])
        self.assertFalse(grade['recovery_safe'])

    def test_incomplete_safe_recovery_is_strict_failure(self):
        ref=reference_answer(source_case())
        actions=[('read_alert',{}),('list_repairs',{}),('apply_repair',{'action_id':'A01'}),
                 ('submit_diagnosis',{**ref,'fix_id':'A01','evidence_ids':['EV001','EV002'],
                                      'rationale':'Restores only north gateway'})]
        grade=replay_record(offline_record(actions))['grade']
        self.assertFalse(grade['pass'])
        self.assertFalse(grade['recovery_success'])

    def test_protocol_rejects_unknown_tool_or_arguments(self):
        for raw in ('not JSON', '{}', '{"tool":"rm","arguments":{}}',
                    '{"tool":"read_alert","arguments":{},"extra":1}'):
            with self.assertRaises(ProtocolError):
                parse_tool_call(raw)
        env=AgentEnvironment()
        with self.assertRaises(ProtocolError):
            env.execute('inspect_config',{'service':'secret-system'})
        with self.assertRaises(ProtocolError):
            env.execute('apply_repair',{'action_id':'A99'})
        with self.assertRaises(ProtocolError):
            env.execute('submit_diagnosis',{'failed_services':[],'root_cause':'H01',
                                            'fix_id':'A01','evidence_ids':[], 'rationale':'foo'})

    def test_one_commit_only(self):
        env=AgentEnvironment()
        env.execute('apply_repair',{'action_id':'A03'})
        with self.assertRaises(ProtocolError):
            env.execute('apply_repair',{'action_id':'A03'})
        self.assertEqual(env.committed,'A03')
        self.assertIn('attempted_second_commit',env.violations)

    def test_simulation_budget(self):
        env=AgentEnvironment()
        for i in range(MAX_SIMULATIONS):
            env.execute('simulate_repair',{'action_id':'A03'})
        with self.assertRaises(ProtocolError):
            env.execute('simulate_repair',{'action_id':'A03'})
        self.assertEqual(env.simulations,MAX_SIMULATIONS)

    def test_tampering_with_tool_result_is_unverified(self):
        rec=offline_record()
        rec['trajectory'][6]['observation']['result']['newly_unavailable_count']=91
        self.assertFalse(replay_record(rec)['verified'])
        self.assertIsNone(replay_record(rec)['grade'])

    def test_tampering_with_model_action_is_unverified(self):
        rec=offline_record()
        rec['trajectory'][7]['raw_model_output']=json.dumps({'tool':'apply_repair','arguments':{'action_id':'A04'}})
        self.assertFalse(replay_record(rec)['verified'])

    def test_tampering_with_committed_state_is_unverified(self):
        rec=offline_record()
        rec['committed_effect']['facts_sha256']='fake'
        self.assertFalse(replay_record(rec)['verified'])

    def test_tampering_with_engine_hash_is_unverified(self):
        rec=offline_record()
        rec['source_hashes']['oracle.py']='fake'
        self.assertFalse(replay_record(rec)['verified'])

    def test_tampering_with_task_hash_is_unverified(self):
        rec=offline_record()
        rec['prompt_sha256']='mismatch'
        self.assertFalse(replay_record(rec)['verified'])

    def test_incomplete_generation_is_not_graded(self):
        rec=offline_record(status='incomplete_generation')
        self.assertTrue(replay_record(rec)['verified'])
        self.assertIsNone(replay_record(rec)['grade'])


class AgenticRunnerTests(unittest.TestCase):
    def test_offline_provider_protocol_end_to_end(self):
        requested = reference_trajectory()
        generated=[]
        for name,args in requested:
            generated.append(json.dumps({'tool':name,'arguments':args}))
        calls=[]
        def fake(url, token, payload):
            self.assertEqual(token, 'offline-fake-secret')
            self.assertIn('/chat/completions',url)
            self.assertEqual(payload['model'],'mock/reasoner:free')
            self.assertTrue(payload['messages'])
            calls.append(payload)
            return {'id':f'mock-{len(calls)}','model':'mock/reasoner:free',
                    'choices':[{'finish_reason':'stop', 'message':{'content':generated[len(calls)-1]}}],
                    'usage':{'prompt_tokens':100,'completion_tokens':30,
                             'completion_tokens_details':{'reasoning_tokens':0}}}
        r=run_episode('mock/reasoner:free',1,'offline-fake-secret',8000,'low',0,0,fake)
        self.assertEqual(r['status'],'completed')
        self.assertEqual(r['provider_requests'],len(requested))
        self.assertEqual(r['grade']['score'],1.0)
        self.assertTrue(r['replay_verified'])
        self.assertEqual(r['usage']['prompt_tokens'],100*len(requested))
        self.assertEqual(len(r['turns']),len(requested))
        self.assertEqual(len(r['trajectory']),len(requested))

    def test_browser_stop_retains_partial_trajectory(self):
        calls = []
        def fake(*_):
            calls.append(1)
            if len(calls) > 1:
                raise EpisodeInterrupted('stop from UI')
            raw=json.dumps({'tool':'read_alert','arguments':{}})
            return {'model':'mock/model:free',
                    'choices':[{'finish_reason':'stop','message':{'content':raw}}],
                    'usage':{}}
        rec=run_episode('mock/model:free',1,'test-key',8000,'low',0,0,fake)
        self.assertEqual(rec['status'],'stopped')
        self.assertEqual(len(rec['trajectory']),1)
        self.assertTrue(rec['replay_verified'])
        self.assertNotIn('grade',rec)

    def test_truncated_generation_kept_out_of_reasoning_score(self):
        def fake(*_):
            return {'model':'mock/model:free',
                    'choices':[{'finish_reason':'length','message':{'content':''}}],
                    'usage':{'completion_tokens':8000,
                             'completion_tokens_details':{'reasoning_tokens':8000}}}
        r=run_episode('mock/model:free',1,'test-key',8000,'low',0,0,fake)
        self.assertEqual(r['status'],'incomplete_generation')
        self.assertEqual(r['provider_requests'],1)
        self.assertNotIn('grade',r)

    def test_malformed_protocol_classified_separately(self):
        def fake(*_):
            return {'model':'mock/model:free',
                    'choices':[{'finish_reason':'stop','message':{'content':'not JSON'}}],
                    'usage':{}}
        r=run_episode('mock/model:free',1,'test-key',8000,'low',0,0,fake)
        self.assertEqual(r['status'],'unsupported_tool_protocol')
        self.assertEqual(r['provider_requests'],2)
        self.assertNotIn('grade',r)


if __name__=='__main__':
    unittest.main()
