"""Provider-reported cumulative input-token budget for one live agent episode.

Providers disclose exact prompt/input usage only in their responses. This is
therefore a *next-request gate*, not a promise that the final request cannot
cross the configured boundary. We never truncate the agent's messages or
mislabel an estimated tokenizer count as provider-billed tokens.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_MAX_INPUT_TOKENS = 1_000_000
MIN_MAX_INPUT_TOKENS = 4_096
MAX_MAX_INPUT_TOKENS = 2_000_000


class InputTokenBudgetExceeded(Exception):
    """An additional model request would exceed the already-reported budget."""


class InputTokenUsageUnavailable(Exception):
    """A prior response omitted usage; further spending cannot be bounded."""


def reported_input_tokens(response: Any) -> int | None:
    """Read response metadata across LangChain's model-response shapes.

    LangChain's wrap_model_call handler commonly returns a ModelResponse whose
    `result` is a list of AIMessage objects; some versions return AIMessage.
    """
    result = getattr(response, 'result', None)
    if result is not None and result is not response:
        value = reported_input_tokens(result)
        if value is not None:
            return value
    if isinstance(response, (list, tuple)):
        seen = [reported_input_tokens(item) for item in response]
        valid = [v for v in seen if v is not None]
        return sum(valid) if valid else None
    usage = response.get('usage_metadata') if isinstance(response, dict) else getattr(response, 'usage_metadata', None)
    if isinstance(usage, dict):
        count = usage.get('input_tokens')
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            return count
    if isinstance(response, dict) and 'result' in response:
        return reported_input_tokens(response['result'])
    return None


@dataclass
class InputTokenBudget:
    limit: int
    used: int = 0
    reported_requests: int = 0
    usage_missing: bool = False

    def __post_init__(self) -> None:
        if not MIN_MAX_INPUT_TOKENS <= self.limit <= MAX_MAX_INPUT_TOKENS:
            raise ValueError('Invalid cumulative input-token limit')

    def before_request(self) -> None:
        if self.usage_missing:
            raise InputTokenUsageUnavailable(
                'Provider omitted input-token usage; cannot enforce the requested budget for another request'
            )
        if self.used >= self.limit:
            raise InputTokenBudgetExceeded(
                f'Input-token budget reached: {self.used:,} / {self.limit:,} reported tokens; no further model request sent'
            )

    def after_response(self, response: Any) -> None:
        value = reported_input_tokens(response)
        if value is None:
            self.usage_missing = True
            print(f'    input tokens: unavailable / {self.limit} (provider did not report usage)', flush=True)
        else:
            self.used += value
            self.reported_requests += 1
            print(f'    input tokens: {self.used} / {self.limit} (cumulative provider-reported)', flush=True)
