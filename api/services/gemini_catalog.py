"""Explicit, server-managed Gemini Developer API model allowlist.

Model names are not discovered via untrusted browser input. Exact IDs must be
validated by an operator before being added to GEMINI_UI_MODELS.
"""
from __future__ import annotations
import os
import re

PREFIX = 'google-ai-studio/'
MODEL_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$')
DEFAULT = 'gemini-3.5-flash-lite,gemma-4-26b-a4b-it,gemma-4-31b-it'  # Gemini pilot verified; Gemma API support documented, live agent trials pending.


def google_key_ready() -> bool:
    return bool((os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY') or '').strip())


def configured_models() -> list[dict]:
    raw = os.getenv('GEMINI_UI_MODELS', DEFAULT)
    names = [x.strip() for x in raw.split(',')]
    valid = list(dict.fromkeys(x for x in names if MODEL_ID.fullmatch(x)))
    return [{'id':PREFIX + name, 'name':'Google AI Studio · ' + name,
             'provider':'google-ai-studio', 'configured':google_key_ready()}
            for name in valid]


def allowed_model_ids() -> set[str]:
    return {x['id'] for x in configured_models()}
