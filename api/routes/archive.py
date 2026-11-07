"""Read-only original-v1 episode access; NEVER regrades historical results.

The v1 grading contract accepted free text in root_cause but compared it
byte-for-byte with an Hxx ID. Old scores remain historical evidence of that
contract, not comparable observations under the prospective v2 evaluation.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from api.services.storage import RESULTS, file_path, _read_records_for

router = APIRouter()
V1_VERSIONS = {
    'RW01': 'publicincident-rw01-v1-langgraph-v1',
    'RW02': 'publicincident-rw02-v1-langgraph-v1',
    'RW03': 'publicincident-rw03-v1-langgraph-v1',
    'RW01V2': 'publicincident-rw01-v2-langgraph-v1',
    'RW02V2': 'publicincident-rw02-v2-langgraph-v1',
    'RW03V2': 'publicincident-rw03-v2-langgraph-v1',
}
FRAMEWORK = 'langchain-create-agent/langgraph-checkpointed'


def _legacy(name: str) -> list[dict]:
    records = _read_records_for(name)
    if (not records or any(not isinstance(r, dict) or
        r.get('benchmark_version') != V1_VERSIONS.get(r.get('task_id')) or
        r.get('agent_framework') != FRAMEWORK for r in records)):
        raise HTTPException(404, 'Not a frozen historical public-incident run')
    return records


@router.get('/api/archive/runs')
def archived_runs():
    items = []
    for path in RESULTS.glob('ui_*.jsonl'):
        if not path.is_file():
            continue
        try:
            records = _legacy(path.name)
        except (HTTPException, OSError):
            continue
        items.append({
            'filename': path.name,
            'records': len(records),
            'tasks': sorted({r['task_id'] for r in records}),
            'archived_contract': 'historical v1/v2 (original saved score)',
            'grade_policy': 'stored historical grade; not regraded against v3',
        })
    return sorted(items, key=lambda x: x['filename'])


@router.get('/api/archive/runs/{filename}')
def archived_run(filename: str):
    records = _legacy(filename)
    return {
        'filename': filename,
        'archived': True,
        'scope': 'Historical v1/v2 episode; not included in active v3 model comparisons',
        'verification_status': 'not independently replayed under current v3 source',
        'records': [
            {'index': i, 'task_id': r['task_id'], 'model': r.get('model_requested'),
             'trial': r.get('trial'), 'status': r.get('status'),
             'stored_grade': r.get('grade'),
             'record_sha256': hashlib.sha256(json.dumps(r, sort_keys=True,
                 ensure_ascii=False).encode('utf-8')).hexdigest()}
            for i, r in enumerate(records)
        ],
    }


@router.get('/api/archive/runs/{filename}/raw.jsonl')
def archived_raw(filename: str):
    _legacy(filename)
    return PlainTextResponse(file_path(filename).read_text(encoding='utf-8'),
        media_type='application/x-ndjson',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'})
