#!/usr/bin/env python3
"""Run Gemini Developer API through the V6CF LangGraph agent contract.

This is an additive provider adapter. Do not modify benchmarks/runner.py:
recorded implementation hashes are verified against that exact source.
Experiments use the same sandbox, tools, rubric, prompt and replay grader.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from benchmarks.native_agent import MAX_MODEL_CALLS, MAX_TOOLS, ACTIVE_TASK_IDS, agent_prompt
from benchmarks.runner import make_native_tools, run_episode
from benchmarks.input_budget import DEFAULT_MAX_INPUT_TOKENS, MIN_MAX_INPUT_TOKENS, MAX_MAX_INPUT_TOKENS


def gemini_graph_factory(env, model_id, token, max_tokens, effort, temperature, delay):
    """Provider-only substitution; graph and tool orchestration stay native."""
    try:
        from langchain.agents import create_agent
        from langchain.agents.middleware import (
            ModelCallLimitMiddleware, ToolCallLimitMiddleware,
            dynamic_prompt, wrap_model_call,
        )
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langgraph.checkpoint.memory import InMemorySaver
    except ImportError as exc:
        raise RuntimeError('Install Gemini adapter: pip install -r requirements-gemini.txt') from exc

    last = [0.0]
    sequence = [0]
    env.graph_request_limit_active = True

    @wrap_model_call
    def monitor_calls(request, handler):
        env.input_token_budget.before_request()
        sequence[0] += 1
        turn = sequence[0]
        env.model_requests_started = turn
        env.model_phases[turn] = env.phase
        print(f'    turn={turn}/{MAX_MODEL_CALLS} · Gemini request ...', flush=True)
        gap = delay - (time.monotonic() - last[0]) if last[0] else 0
        if gap > 0:
            time.sleep(gap)
        try:
            answer = handler(request)
            env.input_token_budget.after_response(answer)
            print(f'    turn={turn}/{MAX_MODEL_CALLS} · Gemini completed', flush=True)
            return answer
        except Exception as exc:
            print(f'    turn={turn}/{MAX_MODEL_CALLS} · Gemini failed ({type(exc).__name__})', flush=True)
            raise
        finally:
            last[0] = time.monotonic()

    @dynamic_prompt
    def workflow_prompt(_request):
        return env.active_system_prompt()

    # The selected Gemini API model must actually support native function calls.
    # No reasoning configuration is translated silently across providers.
    model = ChatGoogleGenerativeAI(
        model=model_id, google_api_key=token,
        temperature=temperature, max_output_tokens=max_tokens,
        max_retries=0,
    )
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
    parser = argparse.ArgumentParser(description='Direct Gemini API agentic experiments; one case per invocation')
    parser.add_argument('--model', required=True, help='Exact Gemini Developer API model ID, e.g. gemini-3.5-flash-lite if available')
    parser.add_argument('--task', choices=sorted(ACTIVE_TASK_IDS), required=True)
    parser.add_argument('--trials', type=int, default=1)
    parser.add_argument('--max-tokens', type=int, default=8000)
    parser.add_argument('--max-input-tokens', type=int, default=DEFAULT_MAX_INPUT_TOKENS)
    parser.add_argument('--temperature', type=float, default=0)
    parser.add_argument('--delay', type=float, default=4)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if not (1 <= args.trials <= 5 and 512 <= args.max_tokens <= 16000
            and MIN_MAX_INPUT_TOKENS <= args.max_input_tokens <= MAX_MAX_INPUT_TOKENS
            and 0 <= args.temperature <= 1 and 3 <= args.delay <= 30):
        parser.error('Invalid generation limits or trial count')
    if any(ch.isspace() for ch in args.model) or not args.model:
        parser.error('Model ID must be a single token')
    token = (os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY') or '').strip()
    if not token:
        parser.error('Set GOOGLE_API_KEY or GEMINI_API_KEY in the environment')
    output = (ROOT / args.output).resolve()
    if output.suffix != '.jsonl' or not output.is_relative_to((ROOT / 'results').resolve()):
        parser.error('Output must be within results/ and end with .jsonl')
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        parser.error(f'Output already exists: {output}. Use a new filename; never rewrite raw trials.')
    print(f'Gemini Developer API · {args.model} · {args.task} · {args.trials} trial(s)', flush=True)
    for trial in range(1, args.trials + 1):
        rec = run_episode(args.task, args.model, trial, token, args.max_tokens,
                          'not_configured', args.temperature, args.delay,
                          graph_factory=gemini_graph_factory, max_input_tokens=args.max_input_tokens)
        rec['provider'] = 'google-ai-studio-gemini-developer-api'
        rec['provider_adapter'] = 'tools/run_gemini.py'
        rec['provider_adapter_implementation_note'] = 'direct Gemini adapter; V6CF source hashes recorded per episode'
        rec['runtime']['packages']['langchain-google-genai'] = _google_version()
        with output.open('a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + '\n')
            f.flush()
        print(f"    score={(rec.get('grade') or {}).get('score')} "
              f"pass={(rec.get('grade') or {}).get('strict_pass')} status={rec['status']}", flush=True)
    print(f'Run saved: {output}', flush=True)


def _google_version():
    from importlib.metadata import PackageNotFoundError, version
    try:
        return version('langchain-google-genai')
    except PackageNotFoundError:
        return None


if __name__ == '__main__':
    main()
