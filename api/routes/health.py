"""Health and live free-model catalog."""
from __future__ import annotations
from datetime import datetime, timezone
import os
from fastapi import APIRouter
from api.services.model_cache import valid_models
from api.services.gemini_catalog import google_key_ready
from api.services.anthropic_catalog import anthropic_key_ready

router = APIRouter()


@router.get('/api/health')
def health():
    return {'status':'ok', 'version':'0.9.21', 'source':'local JSONL + deterministic oracle',
            'key_configured':bool(os.getenv('OPENROUTER_API_KEY')) or google_key_ready() or anthropic_key_ready(),
            'openrouter_key_configured':bool(os.getenv('OPENROUTER_API_KEY')),
            'google_key_configured':google_key_ready(),
            'anthropic_key_configured':anthropic_key_ready(),
            'timestamp_utc':datetime.now(timezone.utc).isoformat()}


@router.get('/api/models')
def models(refresh: bool = False):
    return valid_models(refresh=refresh)

