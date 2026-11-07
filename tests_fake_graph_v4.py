"""Offline reference streamer for V4 tests only. Not provider evidence."""
from types import SimpleNamespace
from benchmarks.spec import reference_trajectory

def scripted_factory(env, *_, premature=False, wrong_fix=False):
    class Scripted:
        def stream(self,_prompt,config,stream_mode):
            steps=list(reference_trajectory(env.task_id))
            if premature:
                pos=next(i for i,(name,__) in enumerate(steps) if name=='prepare_repair')
                steps.insert(pos,('simulate_repair',{'action_id':'A03'}))
            if wrong_fix:
                pos=next(i for i,(name,__) in enumerate(steps) if name=='apply_repair')
                steps[pos]=('apply_repair',{'action_id':'A01'})
                end_name,end_args=steps[-1]
                steps[-1]=(end_name,{**end_args,'fix_id':'A01'})
            for idx,(name,args) in enumerate(steps,1):
                uid=f'offline-v4-{idx}'
                yield {'model':{'messages':[SimpleNamespace(type='ai',content='',
                    tool_calls=[{'id':uid,'name':name,'args':args}],usage_metadata={},
                    response_metadata={},additional_kwargs={},id=uid)]}}
                yield {'tools':{'messages':[SimpleNamespace(type='tool',content=env.execute(name,args,uid))]}}
    return Scripted()
