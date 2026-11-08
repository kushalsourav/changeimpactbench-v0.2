"""Regression gates for active-source selection, direct-fault leakage, and frozen replay."""
import json
import unittest
from pathlib import Path
from benchmarks.native_agent import ACTIVE_TASK_IDS, TASK_IDS, agent_prompt
from benchmarks.spec import get_spec, source_case, service_codes
from benchmarks.environment import AgentEnvironment
from benchmarks.grader import replay_record
from dashboard_data import audit_record
from tests.test_v5_integrated import run_mock
from scripts.v6_ablation_report import condition

ROOT=Path(__file__).resolve().parent.parent

class ActiveSourcesAndEvidence(unittest.TestCase):
    def test_only_original_v4_and_counterfactual_v6_are_active(self):
        expected={f'RW{i:02d}{suffix}' for i in range(1,7) for suffix in ('V4','V6CF')}
        self.assertEqual(ACTIVE_TASK_IDS,expected)
        self.assertIn('RW05V5',TASK_IDS)  # immutable historic source remains readable
        self.assertEqual(condition('RW01V6N'),None)
        self.assertEqual(condition('RW01V6CF'),'v6_counterfactual')

    def test_metrics_and_logs_do_not_announce_direct_fault_for_v6cf(self):
        for i in range(1,7):
            task=f'RW{i:02d}V6CF'
            env=AgentEnvironment(get_spec(task),source_case(task))
            for service in service_codes(task).values():
                metric=env.execute('inspect_metrics',{'service':service})['result']
                log=env.execute('inspect_logs',{'service':service})['result']
                self.assertNotIn('is_direct_local_fault',metric)
                self.assertNotIn('local check violation',str(log))

    def test_direct_fault_requires_config_citation(self):
        for i in (1,3,5):
            task=f'RW{i:02d}V6CF'
            rec=run_mock(task)
            self.assertEqual(rec['grade']['evidence_score'],10)
            self.assertIn('direct-fault configuration',rec['grade']['evidence_review'])
            self.assertTrue(rec['grade']['strict_pass'])
            # Keep the native trace untouched except the *submitted* citations;
            # rebuild a new episode using a graph that only cites metric events.
            rec2=run_mock(task)
            submitted=rec2['final_diagnosis']
            self.assertIn('inspect_config', {step['tool'] for step in rec2['trajectory']})
            self.assertEqual(submitted['root_cause_id'],rec['final_diagnosis']['root_cause_id'])

    def test_metrics_only_citations_do_not_earn_full_local_evidence(self):
        from copy import deepcopy
        from types import SimpleNamespace
        from run_graph_agent import run_episode
        from benchmarks.spec import reference_trajectory

        class MetricCitationGraph:
            def __init__(self, env):
                self.env = env
            def stream(self, _input, config, stream_mode):
                steps = reference_trajectory(self.env.task_id)
                metric_ids = [f'EV{i:03d}' for i, (tool, _) in enumerate(steps, 1)
                              if tool == 'inspect_metrics']
                self_test.assertGreaterEqual(len(metric_ids), 2)
                for i, (tool, args) in enumerate(steps, 1):
                    args=deepcopy(args)
                    if tool == 'submit_diagnosis':
                        # Two valid metric citations and a valid dependency citation.
                        # They must NOT substitute for reading the direct-fault rule.
                        args['evidence_ids'] = metric_ids[:2] + ['EV002']
                    ident=f'negative-{i}'
                    yield {'model': {'messages': [SimpleNamespace(
                        type='ai', content='',
                        tool_calls=[{'name': tool, 'args': args, 'id': ident}],
                        usage_metadata={}, response_metadata={},
                        additional_kwargs={}, id=ident)]}}
                    observation=self.env.execute(tool,args,ident)
                    yield {'tools': {'messages': [SimpleNamespace(type='tool', content=observation)]}}

        self_test = self
        record=run_episode('RW03V6CF', 'mock/metric-only:free',1,'unused-secret',
                           1200,'low',0,3,
                           graph_factory=lambda env,*_: MetricCitationGraph(env))
        self.assertEqual(record['status'],'completed')
        self.assertEqual(record['grade']['evidence_score'],5)
        self.assertFalse(record['grade']['strict_pass'])
        self.assertIn('insufficient_evidence_provenance',
                      record['grade']['strict_failure_reasons'])
        self.assertTrue(replay_record(record)['verified'])

    def test_legacy_counterfactual_records_replayed_in_frozen_source(self):
        path=ROOT/'results/imported/RW05V6CF_claude_2026-11-07.jsonl'
        rec=json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(rec['benchmark_version'],'agentic-v6-counterfactual-1')
        old=replay_record(rec)
        self.assertTrue(old['verified'],old.get('warnings'))
        self.assertTrue(old['grade']['strict_pass'])
        self.assertEqual(audit_record(rec)['status'],'completed')
        self.assertNotEqual(json.loads(agent_prompt('RW05V6CF'))['version'],rec['benchmark_version'])

if __name__=='__main__':unittest.main()
