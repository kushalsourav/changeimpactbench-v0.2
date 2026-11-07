"""Forward native-agent subprocess output to the durable log AND API terminal.

FastAPI does not import or execute LangGraph itself. This small pipe reader
preserves the live SSE/status log while exposing full redacted execution
exceptions to the operator's terminal. The child already redacts credentials.
"""
from __future__ import annotations
import sys
import threading
from pathlib import Path
from subprocess import Popen
from typing import TextIO


def start_log_tee(process: Popen, log_path: Path, console: TextIO | None = None) -> threading.Thread:
    if process.stdout is None:
        raise ValueError('Start child with stdout=subprocess.PIPE and text=True')
    target = console if console is not None else sys.stderr

    def forward() -> None:
        assert process.stdout is not None
        try:
            with log_path.open('a', encoding='utf-8') as saved:
                for line in process.stdout:
                    saved.write(line)
                    saved.flush()
                    try:
                        target.write(f'[ChangeImpactBench agent pid={process.pid}] {line}')
                        target.flush()
                    except (OSError, ValueError):
                        # Closing a terminal must never drop the durable log.
                        pass
        finally:
            process.stdout.close()

    thread = threading.Thread(target=forward, name=f'agent-log-tee-{process.pid}', daemon=True)
    thread.start()
    return thread
