"""OpenRouter public free-model catalog; no LLM workflow or model/tool loop."""
from __future__ import annotations
from decimal import Decimal, InvalidOperation
import json
import urllib.error
import urllib.request
API = "https://openrouter.ai/api/v1"

def get_json(url: str, token: str | None = None, post: dict | None = None) -> dict:
    data = json.dumps(post).encode("utf-8") if post is not None else None
    headers = {"Content-Type": "application/json", "User-Agent": "ChangeImpactBench/0.1"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(
        url, data=data, headers=headers, method="POST" if data is not None else "GET"
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Don't write raw error bodies; providers may reflect request details.
        detail = exc.read(600).decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {exc.code} from OpenRouter: {detail}") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"OpenRouter request failed: {exc}") from None


def fetch_free_models() -> list[dict]:
    raw = get_json(API + "/models")
    free = []
    for d in raw.get("data", []):
        model_id = d.get("id", "")
        pricing = d.get("pricing") or {}
        # Deliberately restrict to free variants, not zero-priced paid-route aliases.
        try:
            free_prices = (
                Decimal(str(pricing.get("prompt", "?"))) == 0
                and Decimal(str(pricing.get("completion", "?"))) == 0
            )
        except (InvalidOperation, TypeError):
            free_prices = False
        if model_id.endswith(":free") and free_prices:
            free.append(
                {
                    "id": model_id,
                    "name": d.get("name", ""),
                    "context_length": d.get("context_length"),
                }
            )
    return sorted(free, key=lambda d: d["id"])

