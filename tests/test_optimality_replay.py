"""Scripted offline counterexamples: strict cost optimum is separate from safe recovery."""
from __future__ import annotations
from benchmarks.grader import replay_record as _legacy_replay
from types import SimpleNamespace
import unittest
from benchmarks.spec import reference_trajectory
from benchmarks.runner import run_episode


def costly_factory(env,*_):
    class Costly:
        def stream(self,_input,config,stream_mode):
            steps=list(reference_trajectory(env.task_id))
            for i,(name,args) in enumerate(steps):
                if name in ('simulate_repair','apply_repair') and args.get('action_id')=='A02':
                    steps[i]=(name,{'action_id':'A04'})
                if name=='submit_diagnosis':
                    steps[i]=(name,{**args,'fix_id':'A04'})
            for i,(name,args) in enumerate(steps,1):
                ident=f'fixture-costly-{i}'
                yield {'model':{'messages':[SimpleNamespace(type='ai',content='',tool_calls=[{'name':name,'args':args,'id':ident}],usage_metadata={},response_metadata={},additional_kwargs={},id=ident)]}}
                yield {'tools':{'messages':[SimpleNamespace(type='tool',content=env.execute(name,args,ident))]}}
    return Costly()

class CostOptimalityReplayTests(unittest.TestCase):
    def test_rw03_safe_expensive_100_weighted_but_strict_fail(self):
        rec=run_episode('RW03V4','offline/costly:free',1,'offline',1024,'low',0,3,graph_factory=costly_factory)
        self.assertEqual(rec['status'],'completed')
        self.assertTrue(rec['replay_verified'])
        g=_legacy_replay(rec)['grade']
        self.assertEqual(g['score'],1.0)
        self.assertTrue(g['recovery_success'])
        self.assertTrue(g['recovery_safe'])
        self.assertFalse(g['fix_correct'])
        self.assertFalse(g['strict_pass'])
        self.assertEqual(g['strict_failure_reasons'],['repair_not_reference_optimal'])
        self.assertEqual(g['committed_action'],'A04')

if __name__=='__main__':unittest.main()
