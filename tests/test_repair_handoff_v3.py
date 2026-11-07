"""Prospective handoff, semantic boundary and error-classification regressions.

The fake graph below emits synthetic TOOL CALLS for offline verification only.
It does not simulate frontier model behavior or constitute a live trial.
"""
from __future__ import annotations
from copy import deepcopy
import contextlib
import io
import json
import unittest

from benchmarks.spec import reference_trajectory
from benchmarks.native_agent import GraphEnvironment, TASK_IDS
from benchmarks.skills import skill_hashes
from benchmarks.grader import replay_record
from benchmarks.runner import (
    classify_execution_error, redact_secret, recursion_step_limit,
    run_episode,
)


def reference_factory(env, *_):
    from types import SimpleNamespace
    class ReferenceGraph:
        def stream(self, _input, config, stream_mode):
            assert config['recursion_limit'] >= 512
            for n, (name, args) in enumerate(reference_trajectory(env.task_id), 1):
                call_id = f'offline-reference-{n}'
                yield {'model': {'messages': [SimpleNamespace(
                    type='ai', content='', tool_calls=[{'id':call_id,'name':name,'args':args}],
                    usage_metadata={}, response_metadata={}, additional_kwargs={}, id=call_id,
                )]}}
                response = env.execute(name, args, call_id)
                yield {'tools': {'messages': [SimpleNamespace(type='tool', content=response)]}}
    return ReferenceGraph()


class GraphRecursionError(Exception):
    pass

class RateLimitError(Exception):
    pass


class RepairHandoffTests(unittest.TestCase):
    def test_all_three_reference_trajectories_have_handoff_and_pass(self):
        self.assertTrue({'RW01V3','RW02V3','RW03V3'}.issubset(TASK_IDS))
        for task in sorted(t for t in TASK_IDS if t.endswith('V3')):
            with self.subTest(task=task):
                record = run_episode(task,'mock/reference:free',1,'offline-secret',1024,'low',0,3,
                    graph_factory=reference_factory)
                self.assertEqual(record['status'],'completed')
                self.assertTrue(record['replay_verified'])
                self.assertTrue(record['grade']['strict_pass'])
                self.assertTrue(record['repair_brief']['repair_instructions'])
                self.assertIn('UNVERIFIED MODEL DATA', record['repair_system_prompt'])
                self.assertEqual(len(record['repair_system_prompt_sha256']),64)
                self.assertTrue(record['grade']['repair_handoff_recorded'])
                self.assertTrue(any(x['tool']=='prepare_repair' for x in record['trajectory']))
                self.assertTrue(any(x['tool']=='apply_repair' for x in record['trajectory']))

    def test_repair_requires_model_authored_handoff(self):
        env = GraphEnvironment('RW01V3')
        for name,args in [('read_alert',{}),('scan_service_health',{}),('list_repairs',{})]:
            self.assertNotIn('rejected',json.loads(env.execute(name,args,'test')))
        for name in ('simulate_repair','apply_repair'):
            response = json.loads(env.execute(name, {'action_id':'A03'},'premature'))
            self.assertTrue(response['rejected'])
            self.assertIn('prepare_repair',response['reason'])
        self.assertEqual(len(env.steps),3)
        self.assertIsNone(env.repair_brief)

    def test_invalid_handoff_is_rejected_without_activation(self):
        env=GraphEnvironment('RW01V3')
        env.execute('read_alert',{},'1')
        env.execute('scan_service_health',{},'2')
        env.execute('list_repairs',{},'3')
        bad = {'failed_services':['mysql-east'], 'hypothesized_root_cause_id':'H03',
               'repair_instructions':'We should investigate the repair effects in our offline sandbox and verify the resulting health before committing.',
               'evidence_ids':['EV999','EV002']}
        response=json.loads(env.execute('prepare_repair',bad,'bad'))
        self.assertTrue(response['rejected'])
        self.assertIsNone(env.repair_brief)
        self.assertEqual(env.phase,'investigation')

    def test_handoff_and_phase_prompt_are_independently_replayed(self):
        record=run_episode('RW01V3','mock/reference:free',1,'offline-secret',1024,'low',0,3,
            graph_factory=reference_factory)
        self.assertTrue(replay_record(record)['verified'])
        for field, change in [
            ('repair_brief', lambda x: x.update({'repair_instructions':'bad'})),
            ('repair_system_prompt', lambda _: None),
            ('repair_system_prompt_sha256', lambda _: None),
        ]:
            bad=deepcopy(record)
            if field=='repair_brief': change(bad[field])
            else: bad[field]='fake-hash-or-prompt'
            self.assertFalse(replay_record(bad)['verified'],field)
        self.assertEqual(len(skill_hashes()),2)
        self.assertTrue(all(len(v)==64 for v in skill_hashes().values()))

    def test_recursion_ceiling_is_graph_steps_not_provider_turns(self):
        self.assertGreaterEqual(recursion_step_limit(48), 48*16)
        self.assertEqual(recursion_step_limit(48),832)

    def test_caught_graph_exception_logged_and_not_mislabeled_api_quota(self):
        def broken_graph(*_):
            class F:
                def stream(self,*_args,**_kwargs):
                    raise GraphRecursionError('Graph exceeded 120 steps')
                    yield  # pragma: no cover
            return F()
        with contextlib.redirect_stderr(io.StringIO()) as buffer:
            rec=run_episode('RW01V3','mock/error:free',1,'super-private-token',1024,'low',0,3,
                            graph_factory=broken_graph)
        self.assertEqual(rec['status'],'orchestration_error')
        self.assertEqual(rec['error_category'],'graph_recursion_limit')
        self.assertIn('GraphRecursionError',rec['error_traceback_redacted'])
        self.assertIn('GraphRecursionError',buffer.getvalue())
        self.assertTrue(rec['replay_verified'])
        self.assertIsNone(rec.get('grade'))
        self.assertNotIn('super-private-token',json.dumps(rec))

    def test_rate_limit_identified_separately_and_secret_redacted(self):
        self.assertEqual(classify_execution_error(RateLimitError('429 requests exceeded')),'provider_rate_limit')
        self.assertNotIn('sk-or-v1-secret123',redact_secret('Authorization: Bearer sk-or-v1-secret123',''))
        def rate_graph(*_):
            class F:
                def stream(self,*_args,**_kwargs):
                    raise RateLimitError('429 OpenRouter daily limit for super-private-token')
                    yield
            return F()
        with contextlib.redirect_stderr(io.StringIO()) as buffer:
            rec=run_episode('RW01V3','mock/rate:free',1,'super-private-token',1024,'low',0,3,
                            graph_factory=rate_graph)
        self.assertEqual(rec['status'],'api_error')
        self.assertEqual(rec['error_category'],'provider_rate_limit')
        self.assertNotIn('super-private-token',json.dumps(rec)+buffer.getvalue())

if __name__=='__main__': unittest.main()
