"""SSE for observable native-agent execution; never contains hidden reasoning."""
from __future__ import annotations
import json
import time
from api.services.process_manager import process_state


def stream_experiment():
    """Send deltas, an initial state, and a terminal event.

    process_state() exposes only a bounded tail of the log; when that tail
    rotates, the client is explicitly instructed to replace its snapshot.
    An idle stream terminates instead of holding one server thread forever.
    """
    previous_run = None
    previous_log = ''
    previous_state = None
    yield ': ChangeImpactBench observable tool-event stream\n\n'
    while True:
        status = process_state()
        current = status.get('id')
        log = status.get('log', '')
        state = {key: value for key, value in status.items() if key != 'log'}
        if current != previous_run:
            previous_run = current
            previous_log = ''
            previous_state = None
        replace = not log.startswith(previous_log)
        delta = log if replace else log[len(previous_log):]
        if delta or state != previous_state:
            payload = {'state': state, 'log_delta': delta, 'replace_log': replace}
            yield 'event: execution\ndata: ' + json.dumps(payload, ensure_ascii=False) + '\n\n'
            previous_state = state
            previous_log = log
        if status.get('status') in ('idle', 'finished', 'error', 'stopped'):
            yield 'event: terminal\ndata: ' + json.dumps({'status': status.get('status')}) + '\n\n'
            break
        time.sleep(1)
