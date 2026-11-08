"""Single subprocess lifecycle and accurate provider-request live monitor."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import re
import threading
import time
from api.services.storage import RESULTS, run_manifest, visible_runs
lock=threading.Lock()
active:dict={}


def _request_counts(full_log: str) -> tuple[int, int, str | None]:
    provider = r'(?:provider|Anthropic|Gemini)'
    started = len(re.findall(rf'^    turn=\d+/\d+ · {provider} request', full_log, flags=re.MULTILINE))
    finished = len(re.findall(rf'^    turn=\d+/\d+ · {provider} (?:completed|failed)', full_log, flags=re.MULTILINE))
    current = re.findall(rf'^    turn=(\d+)/(\d+) · {provider} request', full_log, flags=re.MULTILINE)
    label = f'Provider turn {current[-1][0]} of {current[-1][1]}' if current else None
    return started, min(finished, started), label


def _restored_process_state() -> dict:
    """Reconstruct the newest compatible UI run after process memory is lost."""
    runs = visible_runs()
    if not runs:
        return {'status':'idle'}
    output_path = runs[0]
    manifest = run_manifest(output_path.name) or {}
    log_path = RESULTS / f'{output_path.stem}.log'
    full_log = log_path.read_text(encoding='utf-8', errors='replace') if log_path.is_file() else ''
    records = []
    for line in output_path.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict):
            records.append(item)
    models = manifest.get('models') if isinstance(manifest.get('models'), list) else sorted({
        row.get('model_requested') for row in records if isinstance(row.get('model_requested'), str)
    })
    tasks = manifest.get('tasks') if isinstance(manifest.get('tasks'), list) else [
        next((row.get('task_id') for row in records if isinstance(row.get('task_id'), str)), '')
    ]
    trials = manifest.get('trials') if isinstance(manifest.get('trials'), int) else max(
        (row.get('trial', 0) for row in records if isinstance(row.get('trial'), int)), default=0
    )
    expected_records = len(models) * trials
    complete = expected_records > 0 and len(records) >= expected_records
    started_utc = manifest.get('started_utc') or manifest.get('created_utc')
    elapsed = None
    if isinstance(started_utc, str):
        try:
            started_at = datetime.fromisoformat(started_utc.replace('Z', '+00:00'))
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            end_mtime = max(output_path.stat().st_mtime, log_path.stat().st_mtime if log_path.is_file() else 0)
            elapsed = max(0.0, end_mtime - started_at.timestamp())
        except (ValueError, OSError):
            elapsed = None
    requests_started, requests_finished, _ = _request_counts(full_log)
    return {
        'id': manifest.get('experiment_id') or output_path.stem.removeprefix('ui_'),
        'status': 'finished' if complete else 'stopped',
        'return_code': 0 if complete else None,
        'output_file': output_path.name,
        'started_utc': started_utc,
        'elapsed_seconds': round(elapsed, 1) if elapsed is not None else None,
        'log': full_log[-120000:],
        'requests_planned': manifest.get('requests_planned'),
        'requests_started': requests_started,
        'requests_finished': requests_finished,
        'records_saved': len(records),
        'condition': 'agentic',
        'task_id': tasks[0] if tasks else None,
        'models': models,
        'trials': trials or None,
        'current_request': None,
        'restored_from_disk': True,
    }


def process_state() -> dict:
    with lock:
        if not active:
            return _restored_process_state()
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
        log = full_log[-120000:]
        # The runner emits [n/total] as a request begins. Count these lines on
        # the SERVER, not with browser regexes. A request is finished only after
        # its score or API error has been printed.
        started, finished, current_label = _request_counts(full_log)
        output_path = RESULTS / active['output_file']
        # A durable record can be incomplete while the subprocess is writing it.
        records_saved = 0
        if output_path.exists():
            records_saved = sum(bool(line.strip()) for line in output_path.read_text(encoding='utf-8', errors='replace').splitlines())
        return {'id':active['id'], 'status':status, 'return_code':code,
                'output_file':active['output_file'], 'started_utc':active['started_utc'],
                'elapsed_seconds':round(elapsed, 1) if elapsed is not None else None,
                'log':log, 'requests_planned':active['requests_planned'],
                'requests_started':started, 'requests_finished':finished,
                'records_saved':records_saved,
                'condition':'agentic',
                'task_id':active.get('task_id'), 'models':active.get('models'),
                'trials':active.get('trials'),
                'current_request':current_label if status == 'running' else None}
