"""Hash-bound human evidence adjudication; never changes benchmark grades."""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from api.services.storage import records_for, review_path

router = APIRouter()


class ReviewRequest(BaseModel):
    status: Literal['verified', 'needs_revision', 'uncertain']
    reviewer: str = Field(min_length=2, max_length=80)
    notes: str = Field(min_length=15, max_length=2400)
    oracle_checked: bool = False
    task_grader_alignment_checked: bool = False
    evidence_support_checked: bool = False


@router.post('/api/runs/{filename}/records/{index}/review')
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

