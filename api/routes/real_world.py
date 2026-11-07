"""Source-grounded real-incident API. No synthetic incident endpoints are active."""
from __future__ import annotations
from datetime import datetime,timezone
from pathlib import Path
from typing import Literal
import json,os,re,signal,subprocess,sys,time,uuid
from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse,StreamingResponse
from pydantic import BaseModel,Field,field_validator
from realbench.core import (ENGINE,MAX_MODEL_CALLS,available,case_for,case_summary,
                            public_case,digest,replay)
from realbench.analysis import request_analysis,record_hash,metrics_for
from api.services.model_cache import valid_models
from api.services.process_manager import lock,active,process_state
from api.services.event_stream import stream_experiment
ROOT=Path(__file__).resolve().parents[2]

router=APIRouter()
RESULTS=ROOT/'results'
RESULTS.mkdir(exist_ok=True)
SAFE_FILE=re.compile(r'^ui_[A-Za-z0-9_-]+\.jsonl$')
SAFE_MODEL=re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+:free$')

class LaunchRequest(BaseModel):
    models:list[str]=Field(min_length=1,max_length=3)
    task_id:str
    trials:int=Field(default=1,ge=1,le=3)
    max_tokens:int=Field(default=8000,ge=512,le=16000)
    temperature:float=Field(default=0.0,ge=0,le=1)
    reasoning_effort:Literal['none','minimal','low','medium','high']='low'
    delay:float=Field(default=4.0,ge=3,le=30)
    confirm:bool=False
    @field_validator('models')
    @classmethod
    def models_safe(cls,v):
        if len(v)!=len(set(v)) or any(not SAFE_MODEL.fullmatch(m) for m in v):
            raise ValueError('Choose 1–3 distinct free provider models')
        return v
    @field_validator('task_id')
    @classmethod
    def real_task(cls,v):
        if v not in available():raise ValueError('Choose a published real-world incident')
        return v

class HumanReviewRequest(BaseModel):
    reviewer:str=Field(min_length=2,max_length=90)
    status:Literal['uncertain','verified','needs_revision']='uncertain'
    notes:str=Field(min_length=15,max_length=4000)
    source_checked:bool=False
    tool_evidence_checked:bool=False
    claims_checked:bool=False

class AnalystRequest(BaseModel):
    model_id:str
    confirm:bool=False
    @field_validator('model_id')
    @classmethod
    def valid(cls,v):
        if not SAFE_MODEL.fullmatch(v):raise ValueError('Select a free OpenRouter analyst model')
        return v


def read_records(name):
    if not SAFE_FILE.fullmatch(name):raise HTTPException(400,'Invalid evidence name')
    path=RESULTS/name
    if not path.is_file():raise HTTPException(404,'No saved real-source episode')
    try:
        records=[json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    except (ValueError,OSError):
        raise HTTPException(422,'Invalid JSONL evidence') from None
    if not records or any(r.get('agent_framework')!=ENGINE or r.get('task_id') not in available() or r.get('benchmark_version')!=case_for(r['task_id'])['benchmark_version'] for r in records):
        raise HTTPException(404,'Old synthetic/other-version runs are not part of the real-world dataset')
    return records


def list_records():
    output=[]
    for path in RESULTS.glob('ui_*.jsonl'):
        try:
            records=read_records(path.name)
            output.append({'name':path.name,'count':len(records),
                           'task_id':records[0]['task_id'],
                           'source_title':case_for(records[0]['task_id'])['title'],
                           'models':sorted(set(x['model_requested'] for x in records)),
                           'updated_utc':datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),
                           'completed':sum(x['status']=='completed' for x in records)})
        except (HTTPException,KeyError,ValueError):continue
    return sorted(output,key=lambda x:x['updated_utc'],reverse=True)

@router.get('/api/health')
def health():
    return {'status':'ok','version':'0.9.9','source':'first-party public postmortem excerpts',
            'key_configured':bool(os.environ.get('OPENROUTER_API_KEY')),
            'timestamp_utc':datetime.now(timezone.utc).isoformat()}

@router.get('/api/models')
def models(refresh:bool=False):
    return valid_models(refresh=refresh)

@router.get('/api/tasks')
def tasks():
    return [case_summary(case_for(task)) for task in available()]

@router.get('/api/tasks/{task_id}')
def task(task_id:str):
    try:return case_summary(case_for(task_id))
    except ValueError:raise HTTPException(404,'Unknown published incident') from None

@router.get('/api/tasks/{task_id}/sources')
def source_detail(task_id:str):
    try:
        case=case_for(task_id)
    except ValueError:raise HTTPException(404,'Unknown incident') from None
    return {'id':task_id,'source_url':case['source_url'],'source_title':case['source_title'],
            'source_published':case['source_published'],
            'evidence':[{'id':e['id'],'source_section':e['source_section'],'source_url':e['source_url'],
                        'time':e['time'],'kind':e['kind'],'text':e['text']} for e in case['evidence']],
            'note':'Curated paraphrases of real first-party public postmortems. Not original raw production telemetry.'}

@router.get('/api/runs')
def runs():return list_records()

@router.get('/api/runs/{name}')
def run(name:str):
    records=read_records(name)
    return {'run':name,'records':[{ 'index':i, 'task_id':r['task_id'],
        'model':r['model_requested'],'trial':r['trial'],'status':r['status'],
        'score':(r.get('grade') or {}).get('score'),
        'strict':(r.get('grade') or {}).get('pass'),
        'provider_requests':r.get('provider_requests',0),'elapsed_seconds':r.get('elapsed_seconds',0),
        'timestamp_utc':r['timestamp_utc']} for i,r in enumerate(records)],
        'metrics':metrics_for(records),'source_url':records[0].get('source_url')}

@router.get('/api/runs/{name}/records/{index}')
def record(name:str,index:int):
    records=read_records(name)
    if index<0 or index>=len(records):raise HTTPException(404,'No such episode')
    r=records[index]
    return {'record':r,'audit':replay(r),'source':case_summary(case_for(r['task_id'])),
            'record_sha256':record_hash(r),'index':index}

@router.get('/api/runs/{name}/raw.jsonl')
def raw(name:str):
    read_records(name)
    return FileResponse(RESULTS/name,media_type='application/x-ndjson',filename=name)

@router.get('/api/comparison')
def comparison(task_id:str):
    if task_id not in available():raise HTTPException(404,'Unknown published incident')
    observed=[]
    for path in RESULTS.glob('ui_*.jsonl'):
        try:
            observed.extend(r for r in read_records(path.name) if r['task_id']==task_id)
        except (HTTPException,ValueError):pass
    return {'task_id':task_id,'metrics':metrics_for(observed),
            'source':case_summary(case_for(task_id)),
            'scope':'Version-matched, public postmortem investigation; no real infrastructure actions. Non-gradeable attempts excluded from scored denominator.'}

@router.get('/api/experiment/status')
def status():return process_state()

@router.get('/api/experiment/log/stream')
def sse():
    return StreamingResponse(stream_experiment(),media_type='text/event-stream',
        headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

@router.post('/api/experiment/start',status_code=202)
def launch(req:LaunchRequest):
    if not req.confirm:raise HTTPException(400,'Explicit request-quota approval required')
    token=os.environ.get('OPENROUTER_API_KEY','').strip()
    if not token:raise HTTPException(400,'Server OPENROUTER_API_KEY is missing')
    available_models={m['id'] for m in valid_models()}
    if not set(req.models)<=available_models:
        raise HTTPException(400,'Model unavailable from the current free OpenRouter catalog')
    maximum=len(req.models)*req.trials*MAX_MODEL_CALLS
    with lock:
        current=active.get('process')
        if current is not None and current.poll() is None:raise HTTPException(409,'An experiment is running')
        jid=uuid.uuid4().hex[:12]
        output=f'ui_{jid}.jsonl'
        log_path=RESULTS/f'ui_{jid}.log'
        command=[sys.executable,'-u','-m','realbench.runner','--models',*req.models,
                 '--tasks',req.task_id,'--trials',str(req.trials),
                 '--max-tokens',str(req.max_tokens),'--temperature',str(req.temperature),
                 '--reasoning-effort',req.reasoning_effort,'--delay',str(req.delay),
                 '--max-requests',str(MAX_MODEL_CALLS),'--output',f'results/{output}']
        with log_path.open('w',encoding='utf-8') as handle:
            p=subprocess.Popen(command,stdout=handle,stderr=subprocess.STDOUT,cwd=ROOT,
                               env=os.environ.copy(),start_new_session=True)
        manifest={'schema_version':9,'origin':'first-party postmortem paraphrases',
                  'not_original_telemetry':True,'not_real_infrastructure_repair':True,
                  'experiment_id':jid,'created_utc':datetime.now(timezone.utc).isoformat(),
                  'output_file':output,'models':req.models,'task_id':req.task_id,
                  'trials':req.trials,'max_model_calls_per_episode':MAX_MODEL_CALLS,
                  'requests_planned':maximum,'max_tokens':req.max_tokens,
                  'temperature':req.temperature,'reasoning_effort':req.reasoning_effort,
                  'delay_seconds':req.delay,'dataset_sha256':digest(case_for(req.task_id))}
        (RESULTS/f'ui_{jid}.manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        started=datetime.now(timezone.utc).isoformat()
        active.clear();active.update({'process':p,'id':jid,'output_file':output,'log_path':log_path,
             'requests_planned':maximum,'started_utc':started,'started_monotonic':time.monotonic(),
             'stop_requested':False,'condition':'agentic'})
    return {'id':jid,'status':'running','output_file':output,
            'requests_planned':maximum,'models':len(req.models),'trials':req.trials,
            'started_utc':started}

@router.post('/api/experiment/stop')
def stop():
    with lock:
        p=active.get('process')
        if p is None or p.poll() is not None:raise HTTPException(409,'No running experiment')
        active['stop_requested']=True
        try:os.killpg(p.pid,signal.SIGTERM)
        except ProcessLookupError:pass
    return {'status':'stopping'}


def analysis_path(name,index):
    return RESULTS/(Path(name).stem+f'.{index}.llm-analysis.json')

@router.get('/api/analysis/{name}/{index}')
def get_analysis(name:str,index:int):
    records=read_records(name)
    if index<0 or index>=len(records):raise HTTPException(404,'No episode')
    path=analysis_path(name,index)
    if not path.is_file():return {'status':'not_generated'}
    try:result=json.loads(path.read_text(encoding='utf-8'))
    except ValueError:return {'status':'invalidated'}
    # Cross-run analysis is version+source+record hash scoped, not just a filename.
    valid=(result.get('episode_sha256')==record_hash(records[index])
           and result.get('comparison_hash')==digest([record_hash(r) for r in records]))
    return {'status':'ready',**result} if valid else {'status':'invalidated'}

@router.post('/api/analysis/{name}/{index}')
def analyze(name:str,index:int,request:AnalystRequest):
    if not request.confirm:raise HTTPException(400,'Approve one real additional analyst-provider request')
    token=os.environ.get('OPENROUTER_API_KEY','').strip()
    if not token:raise HTTPException(400,'OPENROUTER_API_KEY missing')
    records=read_records(name)
    if index<0 or index>=len(records):raise HTTPException(404,'No episode')
    try:
        report=request_analysis(records[index],records,request.model_id,token)
    except (ValueError,KeyError,requests.RequestException) as exc:
        raise HTTPException(422,f'LLM analyst could not produce a grounded report: {type(exc).__name__}: {str(exc)[:200]}') from None
    path=analysis_path(name,index)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return {'status':'ready',**report}

@router.get('/api/review/{name}/{index}')
def human_review(name:str,index:int):
    records=read_records(name)
    if index<0 or index>=len(records):raise HTTPException(404,'No episode')
    path=RESULTS/(Path(name).stem+f'.{index}.human-review.json')
    if not path.exists():return {'status':'pending'}
    try:data=json.loads(path.read_text(encoding='utf-8'))
    except ValueError:return {'status':'invalidated'}
    if data.get('episode_sha256')!=record_hash(records[index]):
        return {'status':'invalidated'}
    return data

@router.post('/api/review/{name}/{index}')
def save_human_review(name:str,index:int,form:HumanReviewRequest):
    records=read_records(name)
    if index<0 or index>=len(records):raise HTTPException(404,'No episode')
    if form.status=='verified' and not (form.source_checked and form.tool_evidence_checked and form.claims_checked):
        raise HTTPException(400,'Verified requires independent source, tool and claim checks')
    data={**form.model_dump(),'episode_sha256':record_hash(records[index]),
          'updated_utc':datetime.now(timezone.utc).isoformat(),
          'official_grade_unchanged':True}
    path=RESULTS/(Path(name).stem+f'.{index}.human-review.json')
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return data
