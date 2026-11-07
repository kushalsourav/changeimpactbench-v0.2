#!/usr/bin/env python3
"""Direct Anthropic provider adapter to frozen ChangeImpactBench V4 LangGraph.

Same agent tools, dynamic repair skill, checkpoint, episode recorder, replay
and grader as all other providers. Provider-only change. No hidden retries.
"""
from __future__ import annotations
import argparse
from functools import lru_cache
import json
import os
from pathlib import Path
import signal
import sys
import time
from importlib.metadata import PackageNotFoundError, version

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from benchmarks.native_agent import MAX_MODEL_CALLS, MAX_TOOLS, TASK_IDS, agent_prompt
from benchmarks.runner import make_native_tools, run_episode, _stop_signal
from api.services.anthropic_catalog import MODEL, allowed_model_ids

CACHE = {'type': 'ephemeral'}
NO_FORCED_TOOL_CHOICE_PREFIXES = ('claude-fable-5-1', 'claude-opus-5-5', 'claude-sonnet-5-5')


def normalize_tool_choice(model: str, choice):
    if choice != 'required':
        return choice
    return 'auto' if model.startswith(NO_FORCED_TOOL_CHOICE_PREFIXES) else 'any'


def mark_cache_breakpoints(messages: list) -> list:
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
    result = list(messages)
    indices = [i for i, m in enumerate(result) if isinstance(m, SystemMessage)][:1]
    if result and isinstance(result[-1], (HumanMessage, ToolMessage)):
        indices.append(len(result) - 1)
    for i in dict.fromkeys(indices):
        msg = result[i]
        content = msg.content
        if isinstance(content, str) and content.strip():
            blocks = [{'type': 'text', 'text': content, 'cache_control': CACHE}]
        elif isinstance(content, list) and content:
            blocks = list(content)
            last = blocks[-1]
            if isinstance(last, str):
                blocks[-1] = {'type': 'text', 'text': last, 'cache_control': CACHE}
            elif isinstance(last, dict) and last.get('type') == 'text':
                blocks[-1] = {**last, 'cache_control': CACHE}
            else:
                continue
        else:
            continue
        result[i] = msg.model_copy(update={'content': blocks})
    return result


def drop_stale_investigation_thinking(messages: list) -> list:
    """Drop signed thinking invalidated by the V4 investigation -> repair prompt swap.

    Claude Sonnet 5.5 binds prior thinking signatures to the system prompt.
    V4 intentionally changes the system prompt after `prepare_repair`.
    Keep all visible text, native tool calls, tool results and later repair-phase
    thinking; remove ONLY old investigation-phase thinking/redacted_thinking.
    This is performed on the outgoing provider message copy, not the recorded
    LangGraph messages or deterministic grader inputs.
    """
    from langchain_core.messages import AIMessage, SystemMessage

    in_repair_phase = any(
        isinstance(msg, SystemMessage)
        and isinstance(msg.content, str)
        and '# Active agent skill: repair and verification' in msg.content
        for msg in messages
    )
    if not in_repair_phase:
        return messages

    handoff_index = None
    for index, msg in enumerate(messages):
        if isinstance(msg, AIMessage) and any(
            call.get('name') == 'prepare_repair'
            for call in (msg.tool_calls or [])
        ):
            handoff_index = index
            break
    if handoff_index is None:
        return messages

    out = list(messages)
    for index in range(handoff_index + 1):
        msg = out[index]
        if not isinstance(msg, AIMessage) or not isinstance(msg.content, list):
            continue
        kept = [
            block for block in msg.content
            if not (isinstance(block, dict) and block.get('type')
                    in ('thinking', 'redacted_thinking'))
        ]
        if len(kept) != len(msg.content):
            out[index] = msg.model_copy(update={'content': kept})
    return out


@lru_cache(maxsize=1)
def cached_anthropic_class():
    from langchain_anthropic import ChatAnthropic

    class CachedChatAnthropic(ChatAnthropic):
        def bind_tools(self, tools, *, tool_choice=None, **kwargs):
            # Anthropic defaults to parallel native tool use; V4 requires exactly
            # one tool per model response. Enforce this at the provider API,
            # not by rewriting model trajectories after the fact.
            kwargs['parallel_tool_calls'] = False
            return super().bind_tools(tools, tool_choice=normalize_tool_choice(self.model, tool_choice), **kwargs)

        def invoke(self, input, config=None, *, stop=None, **kwargs):
            if isinstance(input, list):
                input = drop_stale_investigation_thinking(input)
                input = mark_cache_breakpoints(input)
            return super().invoke(input, config=config, stop=stop, **kwargs)

    return CachedChatAnthropic


def anthropic_graph_factory(env, model_id, token, max_tokens, effort, temperature, delay):
    from langchain.agents import create_agent
    from langchain.agents.middleware import (
        ModelCallLimitMiddleware, ToolCallLimitMiddleware, dynamic_prompt, wrap_model_call,
    )
    from langgraph.checkpoint.memory import InMemorySaver

    previous = [0.0]
    sequence = [0]
    env.graph_request_limit_active = True

    @wrap_model_call
    def monitor_calls(request, handler):
        sequence[0] += 1
        turn = sequence[0]
        env.model_requests_started = turn
        env.model_phases[turn] = env.phase
        print(f'    turn={turn}/{MAX_MODEL_CALLS} · Anthropic request ...', flush=True)
        wait = delay - (time.monotonic() - previous[0]) if previous[0] else 0
        if wait > 0:
            time.sleep(wait)
        try:
            answer = handler(request)
            print(f'    turn={turn}/{MAX_MODEL_CALLS} · Anthropic completed', flush=True)
            return answer
        except Exception as exc:
            print(f'    turn={turn}/{MAX_MODEL_CALLS} · Anthropic failed ({type(exc).__name__})', flush=True)
            raise
        finally:
            previous[0] = time.monotonic()

    @dynamic_prompt
    def workflow_prompt(_request):
        return env.active_system_prompt()

    # No substituted sampling defaults or hidden retries. Reasoning effort is
    # not silently translated to provider-specific thinking parameters.
    # Claude Sonnet 5.5 rejects non-default temperature values. Do not
    # forward a sampling parameter the provider does not accept; retain the
    # requested experiment setting in the episode metadata for auditability.
    model_kwargs = dict(model=model_id, api_key=token,
                        max_tokens=max_tokens, max_retries=0)
    if not model_id.startswith(NO_FORCED_TOOL_CHOICE_PREFIXES):
        model_kwargs['temperature'] = temperature
    model = cached_anthropic_class()(**model_kwargs)
    return create_agent(
        model=model, tools=make_native_tools(env),
        system_prompt=agent_prompt(env.task_id),
        middleware=[
            ModelCallLimitMiddleware(run_limit=MAX_MODEL_CALLS, exit_behavior='end'),
            ToolCallLimitMiddleware(run_limit=MAX_TOOLS, exit_behavior='end'),
            workflow_prompt, monitor_calls,
        ],
        checkpointer=InMemorySaver(), name='changeimpactbench_agent',
    )


def main():
    parser = argparse.ArgumentParser(description='Direct Anthropic API with frozen V4 LangGraph tool evaluation')
    parser.add_argument('--model', required=True)
    parser.add_argument('--task', choices=sorted(x for x in TASK_IDS if x.endswith('V4')), required=True)
    parser.add_argument('--trials', type=int, default=1)
    parser.add_argument('--max-tokens', type=int, default=8000)
    parser.add_argument('--temperature', type=float, default=0)
    parser.add_argument('--delay', type=float, default=4)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if 'anthropic/' + args.model not in allowed_model_ids():
        parser.error('Model is not approved for direct Anthropic API evaluations')
    if not (1 <= args.trials <= 5 and 512 <= args.max_tokens <= 16000
            and 0 <= args.temperature <= 1 and 3 <= args.delay <= 30):
        parser.error('Invalid generation limits or trial count')
    token = (os.getenv('ANTHROPIC_API_KEY') or '').strip()
    if not token:
        parser.error('Set ANTHROPIC_API_KEY in backend environment')
    output = (ROOT / args.output).resolve()
    if output.suffix != '.jsonl' or not output.is_relative_to((ROOT / 'results').resolve()):
        parser.error('Output must be within results/ and end with .jsonl')
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        parser.error(f'Output already exists: {output}. Raw evidence must not be overwritten.')
    print(f'Direct Anthropic API · {args.model} · {args.task} · {args.trials} trial(s)', flush=True)
    old = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, _stop_signal)
    try:
        for trial in range(1, args.trials + 1):
            rec = run_episode(args.task, args.model, trial, token, args.max_tokens,
                              'not_configured', args.temperature, args.delay,
                              graph_factory=anthropic_graph_factory)
            rec['provider'] = 'anthropic'
            rec['provider_adapter'] = 'tools/run_anthropic.py'
            rec['provider_adapter_implementation_note'] = 'additive adapter; frozen V4 core source hashes unchanged'
            try:
                rec['runtime']['packages']['langchain-anthropic'] = version('langchain-anthropic')
            except PackageNotFoundError:
                rec['runtime']['packages']['langchain-anthropic'] = None
            with output.open('a', encoding='utf-8') as f:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + '\n')
                f.flush()
            print(f"    score={(rec.get('grade') or {}).get('score')} "
                  f"pass={(rec.get('grade') or {}).get('strict_pass')} status={rec['status']}", flush=True)
        print(f'Run saved: {output}', flush=True)
    finally:
        signal.signal(signal.SIGTERM, old)


if __name__ == '__main__':
    main()
