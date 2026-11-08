"""Saved native-agent evidence, independent audit and reproducible exports."""
from __future__ import annotations
from datetime import datetime, timezone
from benchmarks.spec import source_case
import csv
import io
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, StreamingResponse
from agent_graph import TASK_IDS as GRAPH_TASKS, VERSIONS as GRAPH_VERSIONS, GRAPH_BASE, replay_record as graph_replay
from dashboard_data import audit_record, evidence_rows, summary_rows
from tasks import ROOT
from api.services.storage import visible_runs, records_for, trial_count_for, run_manifest, run_manifest_path, file_path, review_for, review_path
AGENT_TASKS = GRAPH_TASKS

router = APIRouter()

from api.services.storage import visible_runs


@router.get('/api/runs')
def runs():
    out = []
    for path in visible_runs():
        # The runner writes JSONL incrementally. Incomplete lines are ignored only if corrupt.
        try:
            data = records_for(path.name)
        except HTTPException:
            continue
        task_ids = sorted({x.get('task_id', '?') for x in data})
        versions = sorted({x.get('benchmark_version', GRAPH_VERSIONS.get(x.get('task_id'), 'unknown')) for x in data})
        manifest = run_manifest(path.name)
        out.append({'name': path.name, 'records': len(data),
                    'condition': 'agentic',
                    'updated_utc': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                    'models': sorted({x.get('model_requested', '?') for x in data}),
                    'tasks': task_ids, 'benchmark_versions': versions,
                    'planned_trials': manifest.get('trials') if manifest else None,
                    'requests_planned': manifest.get('requests_planned') if manifest else None})
    return out


@router.get('/api/runs/{filename}')
def run_info(filename: str, k: int | None = Query(default=None, ge=1, le=10)):
    records = records_for(filename)
    trial_count, trial_source = trial_count_for(filename, records, k)
    cases = {task_id: source_case(task_id) for task_id in GRAPH_TASKS}
    rows = evidence_rows(records, cases)
    summaries = summary_rows(records, trial_count)
    versions = sorted({r.get('benchmark_version') or GRAPH_VERSIONS.get(r.get('task_id'), 'unknown') for r in records})
    return {'run': filename, 'expected_trials': trial_count,
            'expected_trials_source': trial_source,
            'run_manifest': run_manifest(filename),
            'summary': summaries, 'benchmark_versions': versions,
            'rows': rows, 'record_count': len(records),
            'counts': {'completed': sum(r['status'] == 'completed' for r in rows),
                       'api_errors': sum(r['status'] == 'api_error' for r in rows),
                       'incomplete': sum(r['status'] in ('incomplete_generation', 'empty_generation') for r in rows),
                       'unverified': sum(r['status'] == 'unverified' for r in rows),
                       'agentic_non_gradeable': sum(r['status'] in ('unsupported_tool_protocol', 'budget_exhausted', 'input_budget_exhausted', 'input_usage_unavailable', 'orchestration_error') for r in rows),
                       'unsafe_committed_episodes': sum(r.get('unsafe_commit') is True for r in rows),
                       'human_reviews_verified': sum(review_for(filename, i, r) is not None and review_for(filename, i, r)['status'] == 'verified' for i, r in enumerate(records)),
                       'human_reviews_pending': sum(r.get('task_id') in AGENT_TASKS and (review_for(filename, i, r) is None or review_for(filename, i, r).get('status') != 'verified') for i, r in enumerate(records))}}


@router.get('/api/runs/{filename}/records/{index}')
def run_record(filename: str, index: int):
    records = records_for(filename)
    if index < 0 or index >= len(records):
        raise HTTPException(404, 'Record index not found')
    r = records[index]
    cases = {task_id: source_case(task_id) for task_id in GRAPH_TASKS}
    a = audit_record(r, cases)
    case = cases.get(r.get('task_id'))
    if r.get('task_id') not in GRAPH_TASKS:
        raise HTTPException(422, 'This is not an active LangGraph episode')
    replay = graph_replay(r)
    expected, predicted = replay['expected'], replay['predicted']
    diagnosis = {'expected':expected,'predicted':predicted,'can_parse':bool(predicted),
                 'missed_services':sorted(set(expected['failed_services']) - set((predicted or {}).get('failed_services',[]))),
                 'extra_services':sorted(set((predicted or {}).get('failed_services',[])) - set(expected['failed_services']))}
    reviewer_note = review_for(filename, index, r)
    # Never return .env or provider authorization data. Prompt is public task data.
    return {'human_review': reviewer_note, 'index':index, 'record':r, 'audit':a, 'diagnosis':diagnosis,
            'visible_reasoning_note':'Only publicly returned model output and provider usage are shown; hidden internal reasoning is not accessible.'}


@router.get('/api/runs/{filename}/raw.jsonl')
def export_jsonl(filename: str):
    records_for(filename)  # Reject historical orphan links before reading raw bytes.
    path = file_path(filename)
    return PlainTextResponse(path.read_text(encoding='utf-8'), media_type='application/x-ndjson',
        headers={'Content-Disposition':f'attachment; filename="{filename}"'})


@router.get('/api/runs/{filename}/export.csv')
def export_csv(filename: str):
    records = records_for(filename)
    rows = evidence_rows(records, {task_id: source_case(task_id) for task_id in GRAPH_TASKS})
    buffer = io.StringIO()
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return PlainTextResponse(buffer.getvalue(), media_type='text/csv',
        headers={'Content-Disposition':f'attachment; filename="{Path(filename).stem}.csv"'})


@router.get('/api/runs/{filename}/audit.json')
def export_audit(filename: str):
    """Verified audit export; the browser never invents grader results."""
    records = records_for(filename)
    cases = {task_id: source_case(task_id) for task_id in GRAPH_TASKS}
    rows = evidence_rows(records, cases)
    expected_trials, source = trial_count_for(filename, records)
    return {'run': filename, 'expected_trials': expected_trials,
            'expected_trials_source': source, 'run_manifest': run_manifest(filename),
            'generated_utc': datetime.now(timezone.utc).isoformat(),
            'summary': summary_rows(records, expected_trials),
            'records': [{'index': i, 'raw': r, 'audit': audit_record(r, cases), 'human_review': review_for(filename, i, r)}
                        for i, r in enumerate(records)], 'rows': rows}


@router.get('/api/runs/{filename}/bundle.zip')
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
        seeds = {GRAPH_BASE[task_id] for task_id in included_tasks if task_id in GRAPH_TASKS}
        for seed in sorted(seeds):
            for subdir in ('benchmarks/v6_fixtures/counterfactual', 'reference/v6-counterfactual'):
                path = ROOT / subdir / f'{seed}.json'
                if path.is_file():
                    archive.write(path, f'{subdir}/{seed}.json')
        for file in ('README.md','.env.example','requirements-agent.txt',
                     'requirements-api.txt','requirements.txt',
                     'agent_graph.py','run_graph_agent.py','oracle.py','tasks.py',
                     'benchmarks/native_agent.py','benchmarks/grader.py','benchmarks/runner.py',
                     'benchmarks/input_budget.py',
                     'benchmarks/spec.py','benchmarks/grading_policy.py','benchmarks/environment.py',
                     'api/routes/synthesis.py', 'api/routes/archive.py',
                     'provider_catalog.py','dashboard_data.py','api/main.py',
                     'api/routes/runs.py','api/routes/experiment.py','api/services/storage.py',
                     'tools/audit_benchmark.py','tests/test_v6_counterfactual_release.py'):
            path = ROOT/file
            if path.is_file():
                archive.write(path,file)
        synthesis_file = ROOT/'results'/f'{Path(filename).stem}.synthesis.json'
        if synthesis_file.exists():
            archive.write(synthesis_file, f'results/{synthesis_file.name}')
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

