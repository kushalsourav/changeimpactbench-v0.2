"""Free model discovery cache; no credentials or provider replies in the browser."""
from __future__ import annotations
import time
from fastapi import HTTPException
from provider_catalog import fetch_free_models
from api.services.gemini_catalog import configured_models
from api.services.anthropic_catalog import configured_models as anthropic_models
model_cache: dict = {'at':0.0,'models':[]}

def valid_models(refresh=False):
    if not refresh and time.time() - model_cache['at'] < 900:
        return model_cache['models'] + configured_models() + anthropic_models()
    try:
        values = fetch_free_models()
        model_cache.update({'at':time.time(), 'models':values})
        return values + configured_models() + anthropic_models()
    except Exception as exc:
        # Google remains usable even if the OpenRouter catalog cannot be fetched.
        if configured_models() or anthropic_models():
            return configured_models() + anthropic_models()
        raise HTTPException(503, f'OpenRouter catalog unavailable: {str(exc)[:200]}') from None

