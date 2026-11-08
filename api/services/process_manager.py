"""Single subprocess lifecycle and accurate provider-request live monitor."""
from __future__ import annotations
import re
import threading
import time
from api.services.storage import RESULTS
lock=threading.Lock()
active:dict={}

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
        started = len(re.findall(r'^    turn=\d+/\d+ · (?:provider|Gemini) request', full_log, flags=re.MULTILINE))
        finished = len(re.findall(r'^    turn=\d+/\d+ · (?:provider|Gemini) (?:completed|failed)', full_log, flags=re.MULTILINE))
        current = re.findall(r'^    turn=(\d+)/(\d+) · (?:provider|Gemini) request', full_log, flags=re.MULTILINE)
        current_label = f'Provider turn {current[-1][0]} of {current[-1][1]}' if current else None
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
                'condition':'agentic',
                'task_id':active.get('task_id'), 'models':active.get('models'),
                'trials':active.get('trials'),
                'current_request':current_label if status == 'running' else None}
