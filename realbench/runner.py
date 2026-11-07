"""Native LangChain create_agent / LangGraph execution for real-source investigations.

The model runs one real task per episode; the graph owns model/tool routing.
The collector captures observable calls only, never internal hidden thoughts.
"""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from importlib.metadata import version,PackageNotFoundError
from pathlib import Path
from typing import Annotated,Any
import argparse,json,os,signal,sys,time
from realbench.core import (ENGINE,MAX_MODEL_CALLS,MAX_TOOL_CALLS,case_for,
    prompt_for,digest,source_hashes,EvidenceEnvironment,replay)

try:
    from langchain_core.tools import tool, InjectedToolCallId
except ImportError:
    tool=None
    class InjectedToolCallId: pass

STOP=False

def _stop(_signal,_frame):
    global STOP
    STOP=True
    raise KeyboardInterrupt('Stopped by user')


class NativeEnvironment:
    def __init__(self,case):
        self.underlying=EvidenceEnvironment(case)
        self.provider_turn=0
        self.model_requests_started=0
        self.events=[]
        self.rejected=[]

    def execute(self,name,args,tool_id):
        try:
            observation=self.underlying.execute(name,args)
            self.events.append({'turn':self.provider_turn,'id':tool_id,'observation':observation})
            return json.dumps(observation,ensure_ascii=False)
        except (ValueError,KeyError,TypeError) as exc:
            self.rejected.append({'turn':self.provider_turn,'reason':str(exc)})
            return json.dumps({'rejected':True,'reason':str(exc)},ensure_ascii=False)


def make_tools(env:NativeEnvironment):
    if tool is None:
        raise RuntimeError('Install LangChain and LangGraph: pip install -r requirements-agent.txt')

    @tool
    def read_alert(tool_call_id:Annotated[str,InjectedToolCallId])->str:
        """Read the published incident scenario and neutral diagnosis/impact options."""
        return env.execute('read_alert',{},tool_call_id)

    @tool
    def list_evidence(tool_call_id:Annotated[str,InjectedToolCallId])->str:
        """List indexed source-evidence cards by ID, time and category (not the underlying text)."""
        return env.execute('list_evidence',{},tool_call_id)

    @tool
    def read_evidence(evidence_id:str,tool_call_id:Annotated[str,InjectedToolCallId])->str:
        """Read one E-code excerpt paraphrased from the linked original postmortem."""
        return env.execute('read_evidence',{'evidence_id':evidence_id},tool_call_id)

    @tool
    def inspect_timeline(tool_call_id:Annotated[str,InjectedToolCallId])->str:
        """Examine the available source-backed timeline index, without private production telemetry."""
        return env.execute('inspect_timeline',{},tool_call_id)

    @tool
    def inspect_impact(tool_call_id:Annotated[str,InjectedToolCallId])->str:
        """Inspect possible impact categories; includes affected and unaffected distractors."""
        return env.execute('inspect_impact',{},tool_call_id)

    @tool
    def list_responses(tool_call_id:Annotated[str,InjectedToolCallId])->str:
        """Inspect published-incident response options; does NOT execute any remedy."""
        return env.execute('list_responses',{},tool_call_id)

    @tool(return_direct=True)
    def submit_investigation(impact_ids:list[str],root_cause_id:str,response_id:str,
                             evidence_ids:list[str],rationale:str,
                             tool_call_id:Annotated[str,InjectedToolCallId])->str:
        """FINAL: submit exact affected I-codes, ONE H-code cause, ONE R-code documented action, read E-codes and free-text explanation. ID fields must be IDs, not prose. This does NOT change infrastructure."""
        return env.execute('submit_investigation',dict(impact_ids=impact_ids,
            root_cause_id=root_cause_id,response_id=response_id,
            evidence_ids=evidence_ids,rationale=rationale),tool_call_id)

    return [read_alert,list_evidence,read_evidence,inspect_timeline,inspect_impact,
            list_responses,submit_investigation]


def build_graph(env,model_id,token,max_tokens,effort,temperature,delay):
    from langchain.agents import create_agent
    from langchain.agents.middleware import ModelCallLimitMiddleware,ToolCallLimitMiddleware,wrap_model_call
    from langchain_openrouter import ChatOpenRouter
    from langgraph.checkpoint.memory import InMemorySaver
    previous=[0.0]
    @wrap_model_call
    def monitor(request,handler):
        env.model_requests_started+=1
        turn=env.model_requests_started
        env.provider_turn=turn
        if STOP:
            raise KeyboardInterrupt('Stopped')
        spacing=delay-(time.monotonic()-previous[0]) if previous[0] else 0
        if spacing>0:time.sleep(spacing)
        print(f'    turn={turn}/{MAX_MODEL_CALLS} · provider request',flush=True)
        try:
            response=handler(request)
            print(f'    turn={turn}/{MAX_MODEL_CALLS} · provider completed',flush=True)
            return response
        except Exception as exc:
            print(f'    turn={turn}/{MAX_MODEL_CALLS} · provider failed ({type(exc).__name__})',flush=True)
            raise
        finally:
            previous[0]=time.monotonic()
    model=ChatOpenRouter(model=model_id,api_key=token,max_retries=0,
                         max_tokens=max_tokens,temperature=temperature,
                         reasoning={'effort':effort} if effort and effort!='none' else None)
    return create_agent(model=model,tools=make_tools(env),system_prompt=prompt_for(env.underlying.case),
         middleware=[ModelCallLimitMiddleware(run_limit=MAX_MODEL_CALLS,exit_behavior='end'),
                     ToolCallLimitMiddleware(run_limit=MAX_TOOL_CALLS,exit_behavior='end'),monitor],
         checkpointer=InMemorySaver(),name='cib_real_postmortem_investigator')


def run_episode(task_id,model_id,trial,token,max_tokens=8000,effort='low',
                temperature=0.0,delay=4.0,graph_factory=None):
    case=case_for(task_id)
    env=NativeEnvironment(case)
    now=datetime.now(timezone.utc).isoformat()
    prompt=prompt_for(case)
    record=dict(timestamp_utc=now,task_id=task_id,benchmark_version=case['benchmark_version'],
        agent_framework=ENGINE,source_sha256=digest(case),source_hashes=source_hashes(),
        prompt_sha256=sha256(prompt.encode()).hexdigest(),
        model_requested=model_id,trial=trial,temperature_requested=temperature,
        max_tokens_requested=max_tokens,reasoning_effort_requested=effort,delay_seconds=delay,
        source_url=case['source_url'],source_title=case['source_title'],
        dataset_origin=case['dataset_origin'],
        provider_requests=0,turns=[],trajectory=[],tool_errors=[],final_investigation=None,
        status='incomplete_workflow',grade=None,replay_verified=False,
        hidden_reasoning_available=False,usage={'prompt_tokens':0,'completion_tokens':0})
    start=time.perf_counter()
    try:
        graph=(graph_factory or build_graph)(env,model_id,token,max_tokens,effort,temperature,delay)
        config={'configurable':{'thread_id':f'{task_id}-{model_id}-{trial}-{int(time.time()*1000000)}'},
                'recursion_limit':2*MAX_MODEL_CALLS+MAX_TOOL_CALLS+20}
        for update in graph.stream({'messages':[{'role':'user','content':
                     'Investigate the published incident using source cards, then submit_investigation with I/H/R/E IDs.'}]},
                     config=config,stream_mode='updates'):
            if STOP:raise KeyboardInterrupt('Stopped')
            if not isinstance(update,dict):continue
            if 'model' in update:
                for message in update['model'].get('messages',[]):
                    if getattr(message,'type',None)!='ai':continue
                    # Middleware creates synthetic message on budget exhaustion;
                    # it must NOT be treated as a real provider reply.
                    if len(record['turns']) >= env.model_requests_started:continue
                    calls=[{'id':c.get('id') or '','name':c['name'],'args':c['args']}
                           for c in (getattr(message,'tool_calls',[]) or [])]
                    usage=getattr(message,'usage_metadata',None) or {}
                    exposed=getattr(message,'additional_kwargs',None) or {}
                    record['turns'].append(dict(turn=len(record['turns'])+1,
                        timestamp_utc=datetime.now(timezone.utc).isoformat(),tool_calls=calls,
                        raw_model_output=str(getattr(message,'content',''))[:16000],
                        provider_exposed_reasoning=exposed.get('reasoning_details') or exposed.get('reasoning'),
                        provider_response_id=getattr(message,'id',None),
                        provider_model=(getattr(message,'response_metadata',{}) or {}).get('model_name'),
                        finish_reason=(getattr(message,'response_metadata',{}) or {}).get('finish_reason'),
                        usage=usage))
                    record['usage']['prompt_tokens']+=int(usage.get('input_tokens') or 0)
                    record['usage']['completion_tokens']+=int(usage.get('output_tokens') or 0)
            if 'tools' in update:
                for message in update['tools'].get('messages',[]):
                    if getattr(message,'type',None)=='tool':
                        try:
                            observed=json.loads(str(getattr(message,'content','')))
                            event=observed.get('event_id') or '?'
                            label=observed.get('tool') or 'rejected tool'
                            source=(observed.get('result') or {}).get('id','')
                            print(f'    {event} {label}' + (f' · {source}' if source else ''),flush=True)
                        except (ValueError,TypeError,AttributeError):
                            print('    rejected/unstructured tool response',flush=True)
        if env.underlying.final is not None:record['status']='completed'
        elif env.model_requests_started>=MAX_MODEL_CALLS:record['status']='budget_exhausted'
    except KeyboardInterrupt:
        record['status']='stopped'
    except Exception as exc:
        record['status']='api_error'
        record['error']=(f'{type(exc).__name__}: {str(exc).replace(token,"[REDACTED]")[:300]}')
        print(f'    API error: {type(exc).__name__}',flush=True)
    finally:
        record['elapsed_seconds']=round(time.perf_counter()-start,3)
        record['provider_requests']=len(record['turns'])
        record['model_requests_started']=env.model_requests_started
        record['trajectory']=env.events
        record['tool_errors']=env.rejected
        record['final_investigation']=env.underlying.final
    verification=replay(record)
    record['replay_verified']=verification['verified']
    if verification['grade'] is not None:record['grade']=verification['grade']
    if not verification['verified']:
        record['audit_warnings']=verification['warnings']
        record['status']='unverified'
    return record


def main():
    parser=argparse.ArgumentParser(description='Source-backed LangGraph postmortem evaluation')
    parser.add_argument('--models',nargs='+',required=True)
    parser.add_argument('--tasks',nargs='+',required=True)
    parser.add_argument('--trials',type=int,default=1)
    parser.add_argument('--max-tokens',type=int,default=8000)
    parser.add_argument('--reasoning-effort',default='low')
    parser.add_argument('--temperature',type=float,default=0)
    parser.add_argument('--delay',type=float,default=4)
    parser.add_argument('--max-requests',type=int,default=MAX_MODEL_CALLS)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    if (len(args.models)>4 or len(args.models)<1 or len(args.tasks)!=1
        or args.trials not in (1,2,3) or args.max_requests!=MAX_MODEL_CALLS
        or len(args.models)!=len(set(args.models)) or not all(m.endswith(':free') for m in args.models)):
        raise SystemExit('Choose 1-4 different free models, one source case, 1-3 repeats, 48 calls/episode')
    case_for(args.tasks[0])
    if not (512<=args.max_tokens<=16000 and 0<=args.temperature<=1 and 3<=args.delay<=30):
        raise SystemExit('Invalid generation settings')
    token=os.environ.get('OPENROUTER_API_KEY','').strip()
    if not token:raise SystemExit('Missing OPENROUTER_API_KEY')
    root=Path(__file__).resolve().parent.parent
    output=(root/args.output).resolve()
    if output.parent!=(root/'results').resolve() or output.suffix!='.jsonl':
        raise SystemExit('Output must be in results/*.jsonl')
    output.parent.mkdir(exist_ok=True)
    original=signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM,_stop)
    count=len(args.models)*args.trials
    try:
        n=0
        for model in args.models:
            for trial in range(1,args.trials+1):
                if STOP:break
                n+=1
                print(f'[{n}/{count}] {model} · {args.tasks[0]} · trial {trial} · published source',flush=True)
                record=run_episode(args.tasks[0],model,trial,token,args.max_tokens,
                    args.reasoning_effort,args.temperature,args.delay)
                with output.open('a',encoding='utf-8') as out:
                    out.write(json.dumps(record,ensure_ascii=False,default=str)+'\n')
                print(f'    score={(record.get("grade") or {}).get("score")} pass={(record.get("grade") or {}).get("pass")} status={record["status"]}',flush=True)
        print(f'Run saved: {output}',flush=True)
    finally:
        signal.signal(signal.SIGTERM,original)

if __name__=='__main__':main()
