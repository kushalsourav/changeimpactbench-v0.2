"""Server-approved, direct Anthropic API models; no browser-supplied model IDs."""
from __future__ import annotations
import os

PREFIX = 'anthropic/'
# This exact Anthropic model identifier comes from the supplied working client.
# Catalog inclusion does NOT establish that the provider account can access it.
MODEL = 'claude-sonnet-5-5'

def anthropic_key_ready() -> bool:
    return bool((os.getenv('ANTHROPIC_API_KEY') or '').strip())

def configured_models() -> list[dict]:
    return [{'id': PREFIX + MODEL, 'name': 'Claude Sonnet 5.5 · Anthropic API',
             'provider': 'anthropic', 'configured': anthropic_key_ready()}]

def allowed_model_ids() -> set[str]:
    return {entry['id'] for entry in configured_models()}
