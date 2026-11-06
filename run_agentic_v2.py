#!/usr/bin/env python3
"""Bounded OpenRouter agentic AG08V2 runner. Explicit :free / sandbox only.

One model call emits ONE validated JSON tool request; the Python environment
executes it and returns only its observation on the next turn. No real tools.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import signal
from pathlib import Path
import sys
import time
from typing import Callable

from agentic_v2 import (AgentEnvironment, MAX_TURNS, TASK_ID, VERSION,
                     agent_prompt, digest, implementation_hashes, parse_tool_call, replay_record,
                     source_case, ProtocolError)
from run_eval import API, extract_content, get_json, reasoning_tokens
from tasks import ROOT


class EpisodeInterrupted(Exception):
    """Browser Stop: preserve the trajectory rather than losing the whole run."""


def _stop_signal(_signum, _frame):
    raise EpisodeInterrupted('User stopped sandbox experiment')


def run_episode(model: str, trial: int, token: str, max_tokens: int,
                effort: str | None, temperature: float, delay: float,
                request: Callable = get_json) -> dict:
    prompt = agent_prompt()
    env = AgentEnvironment()
    messages = [
        {'role': 'system', 'content': 'Follow the sandbox JSON-turn protocol exactly. No real infrastructure access. Reply with a single tool call JSON object.'},
        {'role': 'user', 'content': prompt},
    ]
    record = {
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'task_id': TASK_ID, 'benchmark_version': VERSION,
        'model_requested': model, 'trial': trial,
        'temperature_requested': temperature, 'max_tokens_requested': max_tokens,
        'reasoning_effort_requested': effort,
        'prompt': prompt,
        'prompt_sha256': hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
        'case_sha256': digest(source_case()),
        'source_hashes': implementation_hashes(),
        'status': 'budget_exhausted', 'raw_output': '',
        'trajectory': [], 'turns': [], 'final_diagnosis': None,
        'committed_effect': None, 'provider_requests': 0, 'protocol_errors': [],
        'usage': {'prompt_tokens': 0, 'completion_tokens': 0},
        'reasoning_tokens': 0,
    }
    start = time.perf_counter()
    invalid_turns = 0
    try:
        for turn in range(1, MAX_TURNS + 1):
            print(f'    turn={turn}/{MAX_TURNS} · provider request ...', flush=True)
            payload = {'model': model, 'messages': messages,
                       'temperature': temperature, 'max_tokens': max_tokens, 'stream': False}
            if effort:
                payload['reasoning'] = {'effort': effort}
            request_started = time.perf_counter()
            response = request(API + '/chat/completions', token, payload)
            request_elapsed = round(time.perf_counter() - request_started, 3)
            raw, returned, usage = extract_content(response)
            finish = (response.get('choices') or [{}])[0].get('finish_reason')
            record['provider_requests'] += 1
            record['model_returned'] = returned
            record['finish_reason'] = finish
            record['response_id'] = response.get('id')
            for name in ('prompt_tokens', 'completion_tokens'):
                record['usage'][name] += int(usage.get(name) or 0)
            record['reasoning_tokens'] += reasoning_tokens(usage) or 0
            entry = {'turn': turn, 'request_id': response.get('id'), 'model_returned': returned,
                     'raw_model_output': raw, 'finish_reason': finish,
                     'request_elapsed_seconds': request_elapsed,
                     'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                     'usage': usage}
            record['turns'].append(entry)
            record['raw_output'] = raw
            if finish == 'length':
                record['status'] = 'incomplete_generation'
                print('    incomplete_generation: output token budget exhausted', flush=True)
                break
            if not raw.strip():
                record['status'] = 'empty_generation'
                print('    empty_generation: no visible JSON tool call', flush=True)
                break
            try:
                tool, arguments = parse_tool_call(raw)
                observation = env.execute(tool, arguments)
            except ProtocolError as exc:
                invalid_turns += 1
                entry['protocol_error'] = str(exc)
                record['protocol_errors'].append({
                    'turn': turn, 'reason': str(exc),
                    'category': 'premature_submit' if str(exc) == 'Commit a sandbox repair before submitting a diagnosis'
                    else 'rejected_tool_call'})
                print(f'    protocol error: {exc}', flush=True)
                if invalid_turns >= 2:
                    record['status'] = 'unsupported_tool_protocol'
                    break
                messages.append({'role': 'assistant', 'content': raw})
                messages.append({'role': 'user', 'content':
                                 'Tool request rejected: ' + str(exc) +
                                 '. Respond with exactly a valid JSON tool request, no markdown.'})
            else:
                invalid_turns = 0
                entry['tool'] = tool
                entry['arguments'] = arguments
                entry['observation'] = observation
                record['trajectory'].append({**env.steps[-1], 'raw_model_output': raw,
                                              'provider_turn': turn,
                                              'timestamp_utc': entry['timestamp_utc'],
                                              'provider_elapsed_seconds': request_elapsed})
                print(f"    {observation['event_id']} {tool} → {json.dumps(observation['result'])[:160]}", flush=True)
                messages.append({'role': 'assistant', 'content': raw})
                messages.append({'role': 'user', 'content': 'TOOL RESULT (observed, synthetic): ' +
                                 json.dumps(observation, sort_keys=True) +
                                 '\nChoose your next tool action as one JSON object.'})
                if tool == 'submit_diagnosis':
                    record['status'] = 'completed'
                    break
            if turn < MAX_TURNS and delay:
                time.sleep(delay)
    except EpisodeInterrupted:
        record['status'] = 'stopped'
        record['error'] = 'Stopped by user; prior tool observations and any committed safety events are retained'
        print('    stopped: partial agent trajectory retained', flush=True)
    except Exception as exc:
        record['status'] = 'api_error'
        # No raw response bodies, Authorization headers, or secrets in transport logs.
        message = str(exc).replace(token, '[redacted]')
        record['error'] = f'{type(exc).__name__}: {message[:240]}'
        print(f'    API error: {type(exc).__name__}', flush=True)
    finally:
        record['elapsed_seconds'] = round(time.perf_counter() - start, 3)
        record['final_diagnosis'] = env.final
        record['committed_effect'] = env.committed_effect
        record['simulations_used'] = env.simulations
        record['tool_calls'] = len(env.steps)
        record['violations'] = list(env.violations)
    verification = replay_record(record)
    record['replay_verified'] = verification['verified']
    if verification['grade'] is not None:
        record['grade'] = verification['grade']
    if not verification['verified']:
        record['status'] = 'unverified'
        record['audit_warnings'] = verification['warnings']
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description='Isolated AG08 agentic eval; explicit free models only')
    parser.add_argument('--models', nargs='+', required=True)
    parser.add_argument('--tasks', nargs='+', required=True)
    parser.add_argument('--trials', type=int, default=1)
    parser.add_argument('--max-tokens', type=int, default=8000)
    parser.add_argument('--reasoning-effort', default='low')
    parser.add_argument('--temperature', type=float, default=0)
    parser.add_argument('--delay', type=float, default=3)
    parser.add_argument('--max-requests', type=int, default=MAX_TURNS)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.tasks != [TASK_ID] or len(args.models) != 1 or args.trials != 1:
        raise SystemExit('AG08V2 pilot is limited to 1 model × 1 task × 1 episode per launch')
    if not args.models[0].endswith(':free') or args.max_requests < MAX_TURNS:
        raise SystemExit('Only explicit free models and an approved 24-request ceiling are allowed')
    if not 512 <= args.max_tokens <= 16000 or not 0 <= args.temperature <= 1 or not 3 <= args.delay <= 30:
        raise SystemExit('Invalid request limits')
    token = os.getenv('OPENROUTER_API_KEY', '').strip()
    if not token:
        raise SystemExit('OPENROUTER_API_KEY missing; no API calls made')
    path = ROOT / args.output
    path.parent.mkdir(exist_ok=True)
    if path.exists():
        raise SystemExit('Output path already exists; never overwrite experimental evidence')
    print(f'[1/1] {args.models[0]} AG08V2 trial=1 · up to {MAX_TURNS} provider requests, sandbox-only', flush=True)
    signal.signal(signal.SIGTERM, _stop_signal)
    rec = run_episode(args.models[0], 1, token, args.max_tokens,
                      args.reasoning_effort, args.temperature, args.delay)
    with path.open('x', encoding='utf-8') as fp:
        fp.write(json.dumps(rec, ensure_ascii=False) + '\n')
    print(f"    score={(rec.get('grade') or {}).get('score')} pass={(rec.get('grade') or {}).get('pass')} status={rec['status']}", flush=True)
    print(f'Run saved: {path}', flush=True)


if __name__ == '__main__':
    main()
