"""Explicitly approved LangGraph launches and real-time execution monitoring."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
import re
import subprocess
import sys
import time
import uuid
from typing import Literal
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from agent_graph import ACTIVE_TASK_IDS as GRAPH_TASKS, VERSIONS as GRAPH_VERSIONS, MAX_MODEL_CALLS as GRAPH_CALLS, implementation_hashes as graph_hashes
from tasks import ROOT
from api.services.storage import RESULTS, run_manifest_path
from api.services.process_manager import lock, active, process_state
from api.services.model_cache import valid_models
from api.services.gemini_catalog import PREFIX, allowed_model_ids, google_key_ready
from api.services.anthropic_catalog import PREFIX as ANTHROPIC_PREFIX, allowed_model_ids as anthropic_ids, anthropic_key_ready
from api.services.event_stream import stream_experiment
from api.services.log_tee import start_log_tee

router = APIRouter()

SAFE_MODEL = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+:free$')


class LaunchRequest(BaseModel):
    models: list[str] = Field(min_length=1, max_length=5)
    tasks: list[str] = Field(min_length=1, max_length=1)
    trials: int = Field(default=1, ge=1, le=5)
    max_tokens: int = Field(default=8000, ge=512, le=16000)
    reasoning_effort: Literal['none','minimal','low','medium','high'] | None = 'low'
    delay: float = Field(default=4.0, ge=3.0, le=30.0)
    temperature: float = Field(default=0.0, ge=0, le=1)
    confirm: bool = False
    condition: Literal['agentic'] = 'agentic'

    @field_validator('models')
    @classmethod
    def validate_model_ids(cls, values):
        if not 1 <= len(values) <= 5 or len(set(values)) != len(values) or not all(SAFE_MODEL.fullmatch(value) or value in allowed_model_ids() or value in anthropic_ids() for value in values):
            raise ValueError('Choose one to five distinct approved model IDs')
        return values

    @field_validator('tasks')
    @classmethod
    def validate_tasks(cls, values):
        if len(values)!=1 or values[0] not in GRAPH_TASKS:
            raise ValueError('Choose exactly one active LangGraph incident')
        return values


@router.get('/api/experiment/status')
def experiment_status():
    return process_state()


@router.post('/api/experiment/start', status_code=202)
def start_experiment(req: LaunchRequest):
    if not req.confirm:
        raise HTTPException(400, 'Explicit confirmation required before API calls')
    google_models = [x for x in req.models if x.startswith(PREFIX)]
    anthropic_models = [x for x in req.models if x.startswith(ANTHROPIC_PREFIX)]
    openrouter_models = [x for x in req.models if not x.startswith((PREFIX, ANTHROPIC_PREFIX))]
    if anthropic_models and not anthropic_key_ready():
        raise HTTPException(400, 'ANTHROPIC_API_KEY is not loaded on FastAPI server')
    if google_models and not google_key_ready():
        raise HTTPException(400, 'GOOGLE_API_KEY or GEMINI_API_KEY is not loaded on FastAPI server')
    if openrouter_models and not os.getenv('OPENROUTER_API_KEY'):
        raise HTTPException(400, 'OPENROUTER_API_KEY is not loaded on FastAPI server')
    required = GRAPH_CALLS * len(req.models) * req.trials
    google_allowed = allowed_model_ids()
    anthropic_allowed = anthropic_ids()
    openrouter_allowed = {x['id'] for x in valid_models() if x['id'].endswith(':free')} if openrouter_models else set()
    if (any(x not in google_allowed for x in google_models) or
            any(x not in anthropic_allowed for x in anthropic_models) or
            any(x not in openrouter_allowed for x in openrouter_models)):
        raise HTTPException(400, 'One or more models are unavailable or not server-approved')
    google_batch = bool(google_models) and not openrouter_models and not anthropic_models
    anthropic_batch = bool(anthropic_models) and not google_models and not openrouter_models
    with lock:
        p = active.get('process')
        if p is not None and p.poll() is None:
            raise HTTPException(409, 'An experiment is already running')
        jid = uuid.uuid4().hex[:12]
        output_file = f'ui_{jid}.jsonl'
        log_path = RESULTS / f'ui_{jid}.log'
        command = [sys.executable, '-u', str(ROOT / 'tools/run_mixed_providers.py'),
            '--models', *req.models, '--task', req.tasks[0],
            '--trials', str(req.trials), '--delay', str(req.delay),
            '--temperature', str(req.temperature), '--max-tokens', str(req.max_tokens),
            '--reasoning-effort', req.reasoning_effort or 'low',
            '--output', f'results/{output_file}']
        # The subprocess inherits the backend process's environment, not the web browser.
        log_path.write_text('', encoding='utf-8')
        # PIPE -> tee makes full redacted exception tracebacks visible in both
        # the WSL FastAPI terminal and the result log consumed by SSE/monitor.
        p = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             cwd=ROOT, env=os.environ.copy(), start_new_session=True,
                             text=True, encoding='utf-8', errors='replace', bufsize=1)
        start_log_tee(p, log_path)
        manifest = {
            'schema_version': 8, 'condition':'agentic',
            'agent_framework':'langchain-create-agent/langgraph-checkpointed',
            'dataset_origin':'fully synthetic V6 counterfactual; original published incidents used only for inspiration',
            'agentic_source_hashes':graph_hashes(),
            'max_agent_turns':GRAPH_CALLS,
            'source_url': __import__('benchmarks.spec',fromlist=['get_spec']).get_spec(req.tasks[0]).source_url,
            'planned_provider_requests_are_upper_bound':True,
            'experiment_id':jid,'output_file':output_file,
            'created_utc':datetime.now(timezone.utc).isoformat(),
            'models':req.models,'tasks':req.tasks,
            'benchmark_version':GRAPH_VERSIONS[req.tasks[0]],
            'trials':req.trials,'max_tokens':req.max_tokens,
            'reasoning_effort': req.reasoning_effort,
            'google_reasoning_effort_forwarded': False,
            'provider': ('anthropic' if anthropic_batch else 'google-ai-studio-gemini-developer-api' if google_batch else
                         'openrouter' if len(openrouter_models) == len(req.models) else 'mixed'),
            'provider_by_model': {m: ('google-ai-studio' if m.startswith(PREFIX) else 'anthropic' if m.startswith(ANTHROPIC_PREFIX) else 'openrouter') for m in req.models},
            'delay_seconds':req.delay,'temperature':req.temperature,
            'requests_planned':required,
        }
        run_manifest_path(output_file).write_text(
            json.dumps(manifest, indent=2) + '\n', encoding='utf-8'
        )
        started_utc = datetime.now(timezone.utc).isoformat()
        started_monotonic = time.monotonic()
        active.clear()
        active.update({'process':p,'id':jid,'output_file':output_file,
                       'log_path':log_path,'requests_planned':required,
                       'started_utc':started_utc,'started_monotonic':started_monotonic,
                       'stop_requested':False,'condition':req.condition,
                       'task_id':req.tasks[0],'models':req.models,'trials':req.trials})
    return {'id':jid,'status':'running','output_file':output_file,
            'condition':req.condition,'task_id':req.tasks[0],
            'models':req.models,'trials':req.trials,'requests_planned':required,'started_utc':started_utc,'elapsed_seconds':0.0}


@router.post('/api/experiment/stop')
def stop_experiment():
    import signal
    with lock:
        process = active.get('process')
        if not process or process.poll() is not None:
            raise HTTPException(409, 'No active experiment to stop')
        # Terminate the dedicated subprocess session. It performs no destructive cleanup.
        active['stop_requested'] = True
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    return {'status':'stopping', 'message':'Termination requested; completed records remain saved'}


@router.get("/api/experiment/log/stream")
def experiment_stream():
    """Server-sent observable execution events; no model internal reasoning."""
    return StreamingResponse(stream_experiment(), media_type="text/event-stream",
        headers={"Cache-Control":"no-cache", "X-Accel-Buffering":"no"})

