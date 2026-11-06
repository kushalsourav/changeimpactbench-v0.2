"""Local-only FastAPI backend. Works with unchanged eval engine and JSONL evidence.

Security: no shell=True, only free-model IDs, bounded budgets, no secrets exposed,
fixed results directory, localhost development CORS, one subprocess at a time.
"""
from __future__ import annotations

import csv
import hashlib
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import uuid
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from agentic import (TASK_ID as AGENT_TASK, VERSION as AGENT_VERSION, MAX_TURNS as AGENT_TURNS,
                     agent_prompt, digest as agent_digest, source_case as agent_source_case,
                     task_catalog as agent_task_catalog, replay_record as agent_replay,
                     implementation_hashes as agent_source_hashes)
from agentic_v2 import (TASK_ID as AGENT_TASK_V2, VERSION as AGENT_VERSION_V2,
                      MAX_TURNS as AGENT_TURNS_V2, agent_prompt as agent_prompt_v2,
                      source_case as agent_source_case_v2, task_catalog as agent_task_catalog_v2,
                      replay_record as agent_replay_v2,
                      implementation_hashes as agent_source_hashes_v2)
from agentic_v3 import (TASK_ID as AGENT_TASK_V3, VERSION as AGENT_VERSION_V3,
                      MAX_TURNS as AGENT_TURNS_V3, agent_prompt as agent_prompt_v3,
                      source_case as agent_source_case_v3, task_catalog as agent_task_catalog_v3,
                      replay_record as agent_replay_v3,
                      implementation_hashes as agent_source_hashes_v3)
from agentic_suite import (TASK_IDS as SUITE_TASKS, SPECS as SUITE_SPECS,
                           agent_prompt as suite_prompt, source_case as suite_case,
                           task_catalog as suite_catalog, replay_record as suite_replay,
                           implementation_hashes as suite_hashes)
AGENT_TASKS = {AGENT_TASK, AGENT_TASK_V2, AGENT_TASK_V3} | SUITE_TASKS

from dashboard_data import (audit_record, available_runs, case_diagnostics,
                            evidence_rows, expected_trials_from_records,
                            repair_state, summary_rows)
from oracle import reference_answer, reference_audit, initial_failures, patch_facts
from run_eval import effective_status, fetch_free_models
from tasks import ROOT, load_cases, make_prompt

load_dotenv(ROOT / '.env', override=False)
RESULTS = ROOT / 'results'
RESULTS.mkdir(exist_ok=True)
app = FastAPI(title='ChangeImpactBench Evidence API', version='0.9.3')
app.add_middleware(CORSMiddleware,
    allow_origins=['http://localhost:3000','http://127.0.0.1:3000'],
    allow_credentials=False, allow_methods=['GET','POST'], allow_headers=['Content-Type'])

# The API is for local use only. DO NOT deploy publicly without authentication.
lock = threading.Lock()
active: dict = {}
model_cache: dict = {'at': 0.0, 'models': []}
SAFE_FILE = re.compile(r'^[A-Za-z0-9_-]+\.jsonl$')
SAFE_MODEL = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+:free$')


def run_manifest_path(name: str) -> Path:
    """Sidecar created by the UI launcher; never contains tokens or passwords."""
    if not SAFE_FILE.fullmatch(name):
        raise HTTPException(400, 'Invalid results filename')
    return RESULTS / f'{Path(name).stem}.manifest.json'


def run_manifest(name: str) -> dict | None:
    path = run_manifest_path(name)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        return None
    return data if isinstance(data, dict) and data.get('output_file') == name else None


def trial_count_for(name: str, records: list[dict], override: int | None = None) -> tuple[int, str]:
    if override is not None:
        return override, 'explicit'
    manifest = run_manifest(name)
    if manifest is not None and isinstance(manifest.get('trials'), int) and 1 <= manifest['trials'] <= 10:
        return manifest['trials'], 'recorded-at-launch'
    return expected_trials_from_records(records), 'inferred-from-records'


def file_path(name: str) -> Path:
    if not SAFE_FILE.fullmatch(name) or name.startswith('_'):
        raise HTTPException(400, 'Invalid results filename')
    path = RESULTS / name
    if not path.is_file():
        raise HTTPException(404, 'Results file not found')
    return path


def records_for(name: str) -> list[dict]:
    path = file_path(name)
    records = []
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except ValueError as exc:
            raise HTTPException(422, f'Invalid results JSONL on line {number}') from exc
        if isinstance(item, dict):
            records.append(item)
    return records


def valid_models(refresh=False):
    if not refresh and time.time() - model_cache['at'] < 900:
        return model_cache['models']
    try:
        values = fetch_free_models()
        model_cache.update({'at':time.time(), 'models':values})
        return values
    except Exception as exc:
        raise HTTPException(503, f'OpenRouter catalog unavailable: {str(exc)[:200]}') from None


def review_path(filename: str) -> Path:
    # A sidecar, not a modification of raw model evidence.
    return RESULTS / f'{Path(file_path(filename).name).stem}.reviews.json'


def review_for(filename: str, index: int, record: dict) -> dict | None:
    path = review_path(filename)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        item = data.get(str(index))
        expected_sha = hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
        return item if isinstance(item, dict) and item.get('record_sha256') == expected_sha else None
    except (ValueError, OSError, TypeError):
        return None


class ReviewRequest(BaseModel):
    status: Literal['verified', 'needs_revision', 'uncertain']
    reviewer: str = Field(min_length=2, max_length=80)
    notes: str = Field(min_length=15, max_length=2400)
    oracle_checked: bool = False
    task_grader_alignment_checked: bool = False
    evidence_support_checked: bool = False


@app.post('/api/runs/{filename}/records/{index}/review')
def write_review(filename: str, index: int, req: ReviewRequest):
    records = records_for(filename)
    if index < 0 or index >= len(records):
        raise HTTPException(404, 'Record index not found')
    if req.status == 'verified' and not (req.oracle_checked and req.task_grader_alignment_checked and req.evidence_support_checked):
        raise HTTPException(422, 'Verification requires all three human review checks')
    r = records[index]
    path = review_path(filename)
    try:
        notes = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if not isinstance(notes, dict):
            notes = {}
    except (ValueError, OSError):
        notes = {}
    entry = req.model_dump()
    entry.update({
        'record_sha256': hashlib.sha256(json.dumps(r, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest(),
        'updated_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Human review of synthetic evidence; not an independent production incident',
    })
    notes[str(index)] = entry
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(notes, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    os.replace(tmp, path)
    return {'human_review': entry, 'sidecar': path.name}


@app.get('/api/agentic/comparison')
def compare_agentic(task_id: str = 'AG08V3'):
    """Cross-run aggregate, with task VERSION and model settings as strict grouping keys."""
    if task_id not in AGENT_TASKS:
        raise HTTPException(400, 'Choose one agentic task version')
    cases = {c['id']: c for c in load_cases()}
    batches: dict[tuple, dict] = {}
    for path in available_runs():
        try:
            records = records_for(path.name)
        except HTTPException:
            continue
        for index, r in enumerate(records):
            if r.get('task_id') != task_id:
                continue
            key = (r.get('benchmark_version'), r.get('model_requested'),
                   r.get('temperature_requested'), r.get('max_tokens_requested'),
                   r.get('reasoning_effort_requested'))
            item = batches.setdefault(key, {'benchmark_version': key[0], 'model': key[1],
                'temperature': key[2], 'max_tokens': key[3], 'reasoning_effort': key[4],
                'episodes': 0, 'completed': 0, 'strict_passes': 0, 'incomplete_repairs': 0,
                'complete_safe_repairs': 0, 'initial_impact_errors': 0, 'root_cause_errors': 0,
                'repair_selection_errors': 0, 'protocol_error_episodes': 0,
                'unsafe_commits': 0, 'api_errors': 0, 'generation_incomplete': 0,
                'other_non_gradeable': 0, 'unverified': 0, 'human_verified': 0, 'evidence': []})
            item['episodes'] += 1
            a = audit_record(r, cases)
            verified = a['prompt_sha_matches'] is True and a['reference_matches'] is True and a['stored_grade_matches'] is not False
            st = a['status']
            if not verified or st == 'unverified':
                item['unverified'] += 1
                outcome = 'unverified'
            elif st == 'completed' and isinstance(a.get('grade'), dict):
                g = a['grade']
                item['completed'] += 1
                item['strict_passes'] += int(g.get('strict_pass') is True)
                item['incomplete_repairs'] += int(g.get('recovery_safe') is True and g.get('recovery_success') is False)
                item['unsafe_commits'] += int(g.get('unsafe_commit') is True)
                item['complete_safe_repairs'] += int(g.get('recovery_success') is True and g.get('recovery_safe') is True)
                item['initial_impact_errors'] += int(isinstance(g.get('affected_f1'), (float, int)) and g['affected_f1'] < 1)
                item['root_cause_errors'] += int(g.get('root_correct') is False)
                item['repair_selection_errors'] += int(g.get('fix_correct') is False)
                item['protocol_error_episodes'] += int(bool(g.get('protocol_errors')))
                outcome = 'strict_pass' if g.get('strict_pass') is True else ('unsafe_commit' if g.get('unsafe_commit') else 'strict_fail')
            elif st == 'api_error':
                item['api_errors'] += 1
                outcome = 'api_error'
            elif st in ('incomplete_generation', 'empty_generation'):
                item['generation_incomplete'] += 1
                outcome = st
            else:
                item['other_non_gradeable'] += 1
                outcome = st
            note = review_for(path.name, index, r)
            item['human_verified'] += int(note is not None and note['status'] == 'verified')
            item['evidence'].append({'run': path.name, 'index': index, 'status': outcome,
                                     'human_review': note['status'] if note else 'pending'})
    groups = sorted(batches.values(), key=lambda x: (str(x['model']), str(x['reasoning_effort'])))
    for g in groups:
        g['strict_pass_rate_completed'] = (g['strict_passes']/g['completed']) if g['completed'] else None
    return {'task_id': task_id, 'benchmark_version': {
        AGENT_TASK: AGENT_VERSION, AGENT_TASK_V2: AGENT_VERSION_V2,
        AGENT_TASK_V3: AGENT_VERSION_V3, **{k:v['version'] for k,v in SUITE_SPECS.items()}}[task_id],
        'groups': groups, 'scope': 'No pooling across task versions or generation settings. Observational aggregate, not a controlled head-to-head study.'}


@app.get('/api/health')
def health():
    return {'status':'ok', 'version':'0.9.3', 'source':'local JSONL + deterministic oracle',
            'key_configured':bool(os.getenv('OPENROUTER_API_KEY')),
            'timestamp_utc':datetime.now(timezone.utc).isoformat()}


@app.get('/api/runs')
def runs():
    out = []
    for path in available_runs():
        # The runner writes JSONL incrementally. Incomplete lines are ignored only if corrupt.
        try:
            data = records_for(path.name)
        except HTTPException:
            continue
        versions_by_task = {c['id']: c.get('benchmark_version', 'baseline-v0.1') for c in load_cases()}
        task_ids = sorted({x.get('task_id', '?') for x in data})
        versions = sorted({x.get('benchmark_version') or versions_by_task.get(x.get('task_id'), 'unknown') for x in data})
        manifest = run_manifest(path.name)
        out.append({'name': path.name, 'records': len(data),
                    'condition': (manifest or {}).get('condition', 'agentic' if AGENT_TASKS.intersection(task_ids) else 'single-turn'),
                    'updated_utc': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                    'models': sorted({x.get('model_requested', '?') for x in data}),
                    'tasks': task_ids, 'benchmark_versions': versions,
                    'planned_trials': manifest.get('trials') if manifest else None,
                    'requests_planned': manifest.get('requests_planned') if manifest else None})
    return out


@app.get('/api/runs/{filename}')
def run_info(filename: str, k: int | None = Query(default=None, ge=1, le=10)):
    records = records_for(filename)
    trial_count, trial_source = trial_count_for(filename, records, k)
    cases = {c['id']: c for c in load_cases()}
    rows = evidence_rows(records, cases)
    summaries = summary_rows(records, trial_count)
    versions_by_task = {c['id']: c.get('benchmark_version', 'baseline-v0.1') for c in cases.values()}
    versions = sorted({r.get('benchmark_version') or versions_by_task.get(r.get('task_id'), 'unknown') for r in records})
    return {'run': filename, 'expected_trials': trial_count,
            'expected_trials_source': trial_source,
            'run_manifest': run_manifest(filename),
            'summary': summaries, 'benchmark_versions': versions,
            'rows': rows, 'record_count': len(records),
            'counts': {'completed': sum(r['status'] == 'completed' for r in rows),
                       'api_errors': sum(r['status'] == 'api_error' for r in rows),
                       'incomplete': sum(r['status'] in ('incomplete_generation', 'empty_generation') for r in rows),
                       'unverified': sum(r['status'] == 'unverified' for r in rows),
                       'agentic_non_gradeable': sum(r['status'] in ('unsupported_tool_protocol', 'budget_exhausted') for r in rows),
                       'unsafe_committed_episodes': sum(r.get('unsafe_commit') is True for r in rows),
                       'human_reviews_verified': sum(review_for(filename, i, r) is not None and review_for(filename, i, r)['status'] == 'verified' for i, r in enumerate(records)),
                       'human_reviews_pending': sum(r.get('task_id') in AGENT_TASKS and (review_for(filename, i, r) is None or review_for(filename, i, r).get('status') != 'verified') for i, r in enumerate(records))}}


@app.get('/api/runs/{filename}/records/{index}')
def run_record(filename: str, index: int):
    records = records_for(filename)
    if index < 0 or index >= len(records):
        raise HTTPException(404, 'Record index not found')
    r = records[index]
    cases = {c['id']:c for c in load_cases()}
    a = audit_record(r, cases)
    case = cases.get(r.get('task_id'))
    if r.get('task_id') in AGENT_TASKS:
        replay = ({AGENT_TASK: agent_replay, AGENT_TASK_V2: agent_replay_v2, AGENT_TASK_V3: agent_replay_v3, **{k:suite_replay for k in SUITE_TASKS}}[r['task_id']])(r)
        expected, predicted = replay['expected'], replay['predicted']
        diagnosis = {'expected': expected, 'predicted': predicted, 'can_parse': bool(predicted),
                     'missed_services': sorted(set(expected['failed_services']) - set((predicted or {}).get('failed_services', []))),
                     'extra_services': sorted(set((predicted or {}).get('failed_services', [])) - set(expected['failed_services']))}
    else:
        diagnosis = case_diagnostics(r, case) if case else None
    reviewer_note = review_for(filename, index, r)
    # Never return .env or provider authorization data. Prompt is public task data.
    return {'human_review': reviewer_note, 'index':index, 'record':r, 'audit':a, 'diagnosis':diagnosis,
            'visible_reasoning_note':'Only publicly returned model output and provider usage are shown; hidden internal reasoning is not accessible.'}


@app.get('/api/runs/{filename}/raw.jsonl')
def export_jsonl(filename: str):
    path = file_path(filename)
    return PlainTextResponse(path.read_text(encoding='utf-8'), media_type='application/x-ndjson',
        headers={'Content-Disposition':f'attachment; filename="{filename}"'})


@app.get('/api/runs/{filename}/export.csv')
def export_csv(filename: str):
    records = records_for(filename)
    rows = evidence_rows(records, {c['id']:c for c in load_cases()})
    buffer = io.StringIO()
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return PlainTextResponse(buffer.getvalue(), media_type='text/csv',
        headers={'Content-Disposition':f'attachment; filename="{Path(filename).stem}.csv"'})


@app.get('/api/tasks')
def tasks():
    out = []
    for c in load_cases():
        ref = reference_answer(c)
        out.append({'id':c['id'], 'title':c['title'], 'context':c['context'],
                    'services':len(c['facts']['topology']), 'failed':len(ref['failed_services']),
                    'benchmark_version':c.get('benchmark_version','baseline-v0.1')})
    out.extend((agent_task_catalog(), agent_task_catalog_v2(), agent_task_catalog_v3()))
    out.extend(suite_catalog(task_id) for task_id in sorted(SUITE_TASKS))
    return out


@app.get('/api/tasks/{task_id}')
def task_info(task_id: str):
    # Reviewer's reference display is deliberately separate from the agent prompt.
    # The agent does not call HTTP routes: it only sees the bounded tool responses.
    if task_id in AGENT_TASKS:
        versioned = {
            AGENT_TASK: (agent_source_case, AGENT_VERSION, agent_prompt),
            AGENT_TASK_V2: (agent_source_case_v2, AGENT_VERSION_V2, agent_prompt_v2),
            AGENT_TASK_V3: (agent_source_case_v3, AGENT_VERSION_V3, agent_prompt_v3),
            **{k: (lambda k=k: suite_case(k), SUITE_SPECS[k]['version'], lambda k=k: suite_prompt(k)) for k in SUITE_TASKS},
        }
        source, version, prompt_fn = versioned[task_id]
        original = source()
        case = json.loads(json.dumps(original))
        case['id'] = task_id
        case['benchmark_version'] = version
        audit = reference_audit(original)
        for action in original['actions']:
            patched = patch_facts(original['facts'], action)
            direct_after, _ = initial_failures(original['id'], patched)
            audit['actions'][action['id']]['direct_failed_after'] = sorted(direct_after)
        direct_before, _ = initial_failures(original['id'], original['facts'])
        return {'case':case, 'prompt':prompt_fn(), 'reference':reference_answer(original),
                'direct_failed_services':sorted(direct_before), 'audit':audit,
                'condition':'agentic', 'reference_visible_to_agent':False}
    matches = load_cases({task_id}) if task_id in {c['id'] for c in load_cases()} else []
    if not matches:
        raise HTTPException(404, 'Unknown task')
    case = matches[0]
    audit = reference_audit(case)
    for action in case['actions']:
        patched = patch_facts(case['facts'], action)
        direct_after, _ = initial_failures(case['id'], patched)
        audit['actions'][action['id']]['direct_failed_after'] = sorted(direct_after)
    direct_before, _ = initial_failures(case['id'], case['facts'])
    return {'case':case, 'prompt':make_prompt(case), 'reference':reference_answer(case),
            'direct_failed_services':sorted(direct_before), 'audit':audit}


@app.get('/api/models')
def models(refresh: bool = False):
    return valid_models(refresh=refresh)


class LaunchRequest(BaseModel):
    models: list[str] = Field(min_length=1, max_length=4)
    tasks: list[str] = Field(min_length=1, max_length=5)
    trials: int = Field(default=1, ge=1, le=5)
    max_tokens: int = Field(default=8000, ge=512, le=16000)
    reasoning_effort: Literal['none','minimal','low','medium','high'] | None = 'low'
    delay: float = Field(default=4.0, ge=3.0, le=30.0)
    temperature: float = Field(default=0.0, ge=0, le=1)
    confirm: bool = False
    condition: Literal['single-turn', 'agentic'] = 'single-turn'

    @field_validator('models')
    @classmethod
    def validate_model_ids(cls, values):
        if len(values) != len(set(values)) or any(not SAFE_MODEL.fullmatch(m) for m in values):
            raise ValueError('Models must be unique, valid explicit :free identifiers')
        return values

    @field_validator('tasks')
    @classmethod
    def validate_tasks(cls, values):
        allowed = {c['id'] for c in load_cases()} | AGENT_TASKS
        if len(values)!=len(set(values)) or any(x not in allowed for x in values):
            raise ValueError('Unknown or repeated tasks')
        versions = {c.get('benchmark_version','baseline-v0.1') for c in load_cases() if c['id'] in values}
        if AGENT_TASK in values:
            versions.add(AGENT_VERSION)
        if AGENT_TASK_V2 in values:
            versions.add(AGENT_VERSION_V2)
        if AGENT_TASK_V3 in values:
            versions.add(AGENT_VERSION_V3)
        versions.update(SUITE_SPECS[k]['version'] for k in values if k in SUITE_TASKS)
        if len(versions) > 1:
            raise ValueError('Choose tasks from one benchmark version per experiment')
        return values


def process_state() -> dict:
    with lock:
        if not active:
            return {'status':'idle'}
        p = active.get('process')
        code = p.poll() if p else None
        # Capture end time once; repeated polls must not inflate completed runs.
        if code is not None and active.get('finished_monotonic') is None:
            active['finished_monotonic'] = time.monotonic()
        started = active.get('started_monotonic')
        finished = active.get('finished_monotonic')
        elapsed = (max(0.0, (finished if finished is not None else time.monotonic()) - started)
                   if isinstance(started, (int, float)) else None)
        status = ('stopping' if active.get('stop_requested') else 'running') if code is None else ('stopped' if active.get('stop_requested') else ('finished' if code == 0 else 'error'))
        log_path = active['log_path']
        full_log = log_path.read_text(encoding='utf-8', errors='replace') if log_path.exists() else ''
        log = full_log[-14000:]
        # The runner emits [n/total] as a request begins. Count these lines on
        # the SERVER, not with browser regexes. A request is finished only after
        # its score or API error has been printed.
        if active.get('condition') == 'agentic':
            started = len(re.findall(r'^    turn=\d+/\d+ · provider request', full_log, flags=re.MULTILINE))
            finished = len(re.findall(r'^    (?:EV\d+ |protocol error:|incomplete_generation:|empty_generation:|API error:)', full_log, flags=re.MULTILINE))
            current = re.findall(r'^    turn=(\d+)/(\d+) · provider request(.+)$', full_log, flags=re.MULTILINE)
            current_label = f'Agent tool turn {current[-1][0]} of {current[-1][1]}' if current else None
        else:
            started = len(re.findall(r'^\[\d+/\d+\]', full_log, flags=re.MULTILINE))
            finished = len(re.findall(r'^\s+(?:score=|API error:|incomplete_generation:|empty_generation:|Incomplete generation:|Empty generation:)', full_log, flags=re.MULTILINE))
            current = re.findall(r'^\[(\d+)/(\d+)\]\s+(.+)$', full_log, flags=re.MULTILINE)
            current_label = current[-1][2] if current else None
        output_path = RESULTS / active['output_file']
        # A durable record can be incomplete while the subprocess is writing it.
        records_saved = 0
        if output_path.exists():
            records_saved = sum(bool(line.strip()) for line in output_path.read_text(encoding='utf-8', errors='replace').splitlines())
        return {'id':active['id'], 'status':status, 'return_code':code,
                'output_file':active['output_file'], 'started_utc':active['started_utc'],
                'elapsed_seconds':round(elapsed, 1) if elapsed is not None else None,
                'log':log, 'requests_planned':active['requests_planned'],
                'requests_started':started, 'requests_finished':min(finished, started),
                'records_saved':records_saved,
                'condition':active.get('condition', 'single-turn'),
                'current_request':current_label if status == 'running' else None}


@app.get('/api/experiment/status')
def experiment_status():
    return process_state()


@app.post('/api/experiment/start', status_code=202)
def start_experiment(req: LaunchRequest):
    if not req.confirm:
        raise HTTPException(400, 'Explicit confirmation required before API calls')
    if not os.getenv('OPENROUTER_API_KEY'):
        raise HTTPException(400, 'OPENROUTER_API_KEY is not loaded on FastAPI server')
    if req.condition == 'agentic':
        if (len(req.tasks) != 1 or req.tasks[0] not in AGENT_TASKS
            or len(req.models) != 1 or req.trials != 1):
            raise HTTPException(400, 'Agentic pilot supports exactly one model, one versioned task, and one episode per launch')
        required = AGENT_TURNS  # upper bound; real calls may be fewer
    else:
        if AGENT_TASKS.intersection(req.tasks):
            raise HTTPException(400, 'Agentic tasks must use the Agentic investigation condition')
        required = len(req.models)*len(req.tasks)*req.trials
    if required > 45:
        raise HTTPException(400, 'Free-tier safety limit: maximum 45 requests per launch')
    allowed = {x['id'] for x in valid_models()}
    if any(x not in allowed for x in req.models):
        raise HTTPException(400, 'One or more models are unavailable or not a zero-priced free variant')
    with lock:
        p = active.get('process')
        if p is not None and p.poll() is None:
            raise HTTPException(409, 'An experiment is already running')
        jid = uuid.uuid4().hex[:12]
        output_file = f'ui_{jid}.jsonl'
        log_path = RESULTS / f'ui_{jid}.log'
        command = [sys.executable, '-u', str(ROOT / (('run_agentic_suite.py' if req.tasks[0] in SUITE_TASKS else 'run_agentic_v3.py' if req.tasks == [AGENT_TASK_V3] else 'run_agentic_v2.py' if req.tasks == [AGENT_TASK_V2] else 'run_agentic.py')
                              if req.condition == 'agentic' else 'run_eval.py')),
            '--models',*req.models, '--tasks',*req.tasks,
            '--trials',str(req.trials),'--delay',str(req.delay),
            '--temperature',str(req.temperature),'--max-tokens',str(req.max_tokens),
            '--max-requests',str(required), '--output',f'results/{output_file}']
        if req.reasoning_effort:
            command += ['--reasoning-effort',req.reasoning_effort]
        # The subprocess inherits the backend process's environment, not the web browser.
        with log_path.open('w', encoding='utf-8') as f:
            p = subprocess.Popen(command, stdout=f, stderr=subprocess.STDOUT,
                                 cwd=ROOT, env=os.environ.copy(), start_new_session=True)
        manifest = {
            'schema_version': 5 if req.tasks[0] in SUITE_TASKS else 4 if req.tasks == [AGENT_TASK_V3] else 3 if req.tasks == [AGENT_TASK_V2] else 2 if req.condition == 'agentic' else 1,
            'condition': req.condition,
            'agentic_source_hashes': (suite_hashes() if req.tasks[0] in SUITE_TASKS else agent_source_hashes_v3() if req.tasks == [AGENT_TASK_V3] else agent_source_hashes_v2() if req.tasks == [AGENT_TASK_V2]
                                      else agent_source_hashes() if req.condition == 'agentic' else None),
            'max_agent_turns': AGENT_TURNS if req.condition == 'agentic' else None,
            'planned_provider_requests_are_upper_bound': req.condition == 'agentic',
            'experiment_id': jid,
            'output_file': output_file,
            'created_utc': datetime.now(timezone.utc).isoformat(),
            'models': req.models,
            'tasks': req.tasks,
            'benchmark_version': (SUITE_SPECS[req.tasks[0]]['version'] if req.tasks[0] in SUITE_TASKS else AGENT_VERSION_V3 if req.tasks == [AGENT_TASK_V3] else AGENT_VERSION_V2 if req.tasks == [AGENT_TASK_V2] else AGENT_VERSION) if req.condition == 'agentic' else next(
                c.get('benchmark_version', 'baseline-v0.1')
                for c in load_cases() if c['id'] == req.tasks[0]
            ),
            'trials': req.trials,
            'max_tokens': req.max_tokens,
            'reasoning_effort': req.reasoning_effort,
            'delay_seconds': req.delay,
            'temperature': req.temperature,
            'requests_planned': required,
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
                       'stop_requested':False,'condition':req.condition})
    return {'id':jid,'status':'running','output_file':output_file,
            'condition':req.condition,'requests_planned':required,'started_utc':started_utc,'elapsed_seconds':0.0}

@app.get('/api/runs/{filename}/audit.json')
def export_audit(filename: str):
    """Verified audit export; the browser never invents grader results."""
    records = records_for(filename)
    cases = {c['id']: c for c in load_cases()}
    rows = evidence_rows(records, cases)
    expected_trials, source = trial_count_for(filename, records)
    return {'run': filename, 'expected_trials': expected_trials,
            'expected_trials_source': source, 'run_manifest': run_manifest(filename),
            'generated_utc': datetime.now(timezone.utc).isoformat(),
            'summary': summary_rows(records, expected_trials),
            'records': [{'index': i, 'raw': r, 'audit': audit_record(r, cases), 'human_review': review_for(filename, i, r)}
                        for i, r in enumerate(records)], 'rows': rows}


@app.get('/api/runs/{filename}/bundle.zip')
def export_bundle(filename: str):
    """A small reproducibility bundle with actual records, tasks and oracle references."""
    from zipfile import ZipFile, ZIP_DEFLATED
    records = records_for(filename)
    blob = io.BytesIO()
    with ZipFile(blob, 'w', ZIP_DEFLATED) as archive:
        archive.writestr(f'results/{filename}', file_path(filename).read_bytes())
        manifest_file = run_manifest_path(filename)
        if run_manifest(filename) is not None:
            archive.write(manifest_file, f'results/{manifest_file.name}')
        included_tasks = {r.get('task_id') for r in records}
        if AGENT_TASKS.intersection(included_tasks):
            seeds = {'T08' if task in {AGENT_TASK, AGENT_TASK_V2, AGENT_TASK_V3}
                     else SUITE_SPECS[task]['seed']
                     for task in included_tasks if task in AGENT_TASKS}
            for subdir in ('tasks', 'reference'):
                for seed in sorted(seeds):
                    path = ROOT / subdir / f'{seed}.json'
                    if path.is_file():
                        archive.write(path, f'{subdir}/{seed}.json')
        for sub in ('tasks', 'reference'):
            for task_id in sorted(included_tasks):
                if not isinstance(task_id, str) or not re.fullmatch(r'T\d{2}', task_id):
                    continue
                path = ROOT / sub / f'{task_id}.json'
                if path.is_file():
                    archive.write(path, f'{sub}/{path.name}')
        for file in ('README.md', 'run_eval.py', 'grader.py', 'oracle.py',
                     'tasks.py', 'dashboard_data.py', 'analyze.py', 'requirements.txt',
                     'requirements-api.txt', '.env.example', 'api/main.py',
                     'agentic.py', 'run_agentic.py', 'docs/AGENTIC_EVAL_IMPLEMENTATION_v0.6.md',
                     'agentic_v2.py', 'run_agentic_v2.py', 'docs/AG08_V2_EVALUATION_v0.7.md',
                     'agentic_v3.py', 'run_agentic_v3.py', 'docs/RESEARCH_STORY_v0.8.md',
                     'tests/test_agentic_v3.py', 'api/tests/test_research_v08.py',
                     'api/tests/test_research_v09.py', 'docs/FOUR_TAB_RESEARCH_UI_v0.9.md',
                     'web/lib/episode-analysis.ts', 'web/tests/episode-analysis.test.cjs',
                     'web/tests/navigation.test.cjs', 'agentic_suite.py', 'run_agentic_suite.py',
                     'tests/test_agentic_suite.py', 'docs/AGENTIC_SUITE_v0.9.3.md'):
            path = ROOT / file
            if path.exists():
                archive.write(path, file)
        review_file = review_path(filename)
        if review_file.is_file():
            archive.write(review_file, f'results/{review_file.name}')
        archive.writestr('REPRODUCIBILITY.txt',
             'ChangeImpactBench evidence bundle. Raw results + reference tasks + grader.\n'
             'For the complete runnable benchmark and exact execution instructions, use the project README.\n'
             'Review each model and task version before comparing results.\n')
    blob.seek(0)
    return StreamingResponse(blob, media_type='application/zip',
        headers={'Content-Disposition':f'attachment; filename="{Path(filename).stem}_evidence.zip"'})


@app.post('/api/experiment/stop')
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
