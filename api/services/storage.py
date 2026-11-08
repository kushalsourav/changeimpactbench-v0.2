"""Typed evidence-file paths, manifests, and hash-bound human review notes."""
from __future__ import annotations
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
from fastapi import HTTPException
from dashboard_data import expected_trials_from_records
from tasks import ROOT
RESULTS = ROOT / 'results'
RESULTS.mkdir(exist_ok=True)
SAFE_FILE = re.compile(r'^[A-Za-z0-9_-]+\.jsonl$')

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


def _read_records_for(name: str) -> list[dict]:
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



def _loadable_record(record: dict) -> bool:
    """Accept compatible saved evidence even when its source snapshot is older.

    Source hashes are verified by the independent replay/audit layer. Hiding a
    hash-mismatched record here made durable results disappear after any code
    update and prevented the UI from showing the appropriate unverified state.
    """
    from agent_graph import ACTIVE_TASK_IDS, VERSIONS, ENGINE
    task = record.get('task_id')
    return (task in ACTIVE_TASK_IDS and record.get('benchmark_version') == VERSIONS[task]
            and record.get('agent_framework') == ENGINE)


def visible_runs() -> list[Path]:
    """List compatible evidence; replay reports stale source snapshots safely."""
    visible = []
    for path in RESULTS.glob('*.jsonl'):
        if not path.is_file() or not SAFE_FILE.fullmatch(path.name) or path.name.startswith('_'):
            continue
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
            records = [json.loads(line) for line in lines if line.strip()]
        except (OSError, ValueError):
            continue
        if records and all(isinstance(r, dict) and _loadable_record(r) for r in records):
            visible.append(path)
    return sorted(visible, key=lambda path: path.stat().st_mtime, reverse=True)


def records_for(name: str) -> list[dict]:
    """Version-scoped evidence; source drift is surfaced by audit, not hidden."""
    rows = _read_records_for(name)
    if not rows or not all(_loadable_record(row) for row in rows):
        raise HTTPException(404, 'No active LangGraph episode at this evidence path')
    return rows
