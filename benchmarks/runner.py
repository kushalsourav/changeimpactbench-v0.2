#!/usr/bin/env python3
"""REAL LangChain create_agent/LangGraph runtime for prospective tasks only.

No home-grown model/tool orchestration loop: create_agent owns the loop, tool
routing, state, and its in-process checkpoint. This file only observes graph
stream updates and persists the observable provider/tool trajectory. The
independent replay in benchmarks/grader.py NEVER calls an LLM.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import PackageNotFoundError, version as package_version
import json
import os
from pathlib import Path
import signal
import re
import traceback
import sys
import time
from typing import Annotated, Callable, Any, Literal

# IMPORTANT: LangChain resolves @tool annotations with typing.get_type_hints,
# which uses the *defining module*'s namespace, not make_native_tools locals.
# A function-local import causes NameError: InjectedToolCallId during schema
# construction. Keep these names module-global without making offline audits
# depend on LangChain being installed.
try:
    from langchain_core.tools import tool, InjectedToolCallId
except ImportError:  # offline deterministic replay/tests require no LLM packages
    tool = None
    InjectedToolCallId = None

from benchmarks.skills import repair_system_prompt
from agent_graph import (
    ENGINE, GRAPH_BASE, MAX_MODEL_CALLS, MAX_TOOLS, TASK_IDS, VERSIONS,
    GraphEnvironment, agent_prompt, digest, implementation_hashes, recorded_implementation_hashes,
    replay_record, source_case,
)
from tasks import ROOT
from benchmarks.grading_policy import replay_record as active_replay_record, contract_for
from benchmarks.input_budget import (
    InputTokenBudget, InputTokenBudgetExceeded, InputTokenUsageUnavailable,
    DEFAULT_MAX_INPUT_TOKENS, MIN_MAX_INPUT_TOKENS, MAX_MAX_INPUT_TOKENS,
)


class EpisodeInterrupted(Exception):
    pass


def _stop_signal(_signal, _frame):
    raise EpisodeInterrupted('Browser stopped experiment')


def make_native_tools(env: GraphEnvironment) -> list:
    """Native LangChain tool schemas, with injected tool IDs for audit replay."""
    if tool is None or InjectedToolCallId is None:
        raise RuntimeError('Native tool dependency missing: pip install -r requirements-agent.txt')

    @tool
    def read_alert(tool_call_id: Annotated[str, InjectedToolCallId]) -> str:
        """Read the original synthetic incident alert and neutral hypotheses."""
        return env.execute('read_alert', {}, tool_call_id)

    @tool
    def scan_service_health(tool_call_id: Annotated[str, InjectedToolCallId]) -> str:
        """One INITIAL snapshot of external entrypoint probes only; internal impact needs investigation."""
        return env.execute('scan_service_health', {}, tool_call_id)

    @tool
    def inspect_metrics(service: str, tool_call_id: Annotated[str, InjectedToolCallId]) -> str:
        """Inspect timestamped health metrics for ONE named synthetic service."""
        return env.execute('inspect_metrics', {'service': service}, tool_call_id)

    @tool
    def inspect_logs(service: str, tool_call_id: Annotated[str, InjectedToolCallId]) -> str:
        """Read synthetic log messages for ONE named service."""
        return env.execute('inspect_logs', {'service': service}, tool_call_id)

    @tool
    def inspect_config(service: str, tool_call_id: Annotated[str, InjectedToolCallId]) -> str:
        """Inspect ONE service's raw timestamped configuration snapshot; no oracle predicate is exposed."""
        return env.execute('inspect_config', {'service': service}, tool_call_id)

    @tool
    def inspect_dependencies(service: str, tool_call_id: Annotated[str, InjectedToolCallId]) -> str:
        """Inspect ONE service's upstream dependencies and direct consumers, including quorum rules."""
        return env.execute('inspect_dependencies', {'service': service}, tool_call_id)

    @tool
    def list_repairs(tool_call_id: Annotated[str, InjectedToolCallId]) -> str:
        """List candidate operational responses, modeled cost/time/risk and intent; hidden field edits and effects are not exposed."""
        return env.execute('list_repairs', {}, tool_call_id)

    @tool
    def prepare_repair(
        failed_services: list[str],
        hypothesized_root_cause_id: Literal['H01','H02','H03','H04','H05','H06'],
        repair_instructions: str, evidence_ids: list[str],
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> str:
        """HANDOFF: author your own evidence-backed repair plan after investigating and listing repairs. Requires observed evidence IDs, initial failed services and proposed cause. Activates repair-verification skill; NO action is committed."""
        return env.execute('prepare_repair', {
            'failed_services': failed_services,
            'hypothesized_root_cause_id': hypothesized_root_cause_id,
            'repair_instructions': repair_instructions,
            'evidence_ids': evidence_ids,
        }, tool_call_id)

    @tool
    def simulate_repair(action_id: str, tool_call_id: Annotated[str, InjectedToolCallId]) -> str:
        """Read-only counterfactual: predict restored, remaining, and NEW outages for one candidate."""
        return env.execute('simulate_repair', {'action_id': action_id}, tool_call_id)

    @tool
    def apply_repair(action_id: str, tool_call_id: Annotated[str, InjectedToolCallId]) -> str:
        """Commit ONE repair to the isolated synthetic Python simulator; never real infrastructure."""
        return env.execute('apply_repair', {'action_id': action_id}, tool_call_id)

    @tool(return_direct=True)
    def submit_diagnosis(
        failed_services: list[str],
        root_cause_id: Literal['H01','H02','H03','H04','H05','H06'],
        root_cause_explanation: str, fix_id: str,
        evidence_ids: list[str], rationale: str,
        tool_call_id: Annotated[str, InjectedToolCallId],
    ) -> str:
        """FINAL: root_cause_id MUST be a hypothesis ID (H01-H06); root_cause_explanation describes observed causes. Also submit initial failed services, fix ID, real event IDs, and rationale."""
        return env.execute('submit_diagnosis', {
            'failed_services': failed_services, 'root_cause_id': root_cause_id,
            'root_cause_explanation': root_cause_explanation, 'fix_id': fix_id, 'evidence_ids': evidence_ids, 'rationale': rationale,
        }, tool_call_id)

    return [read_alert, scan_service_health, inspect_metrics, inspect_logs,
            inspect_config, inspect_dependencies, list_repairs,
            prepare_repair, simulate_repair, apply_repair, submit_diagnosis]


def build_graph(env: GraphEnvironment, model_id: str, token: str,
                max_tokens: int, effort: str | None, temperature: float, delay: float):
    """One create_agent per episode; the graph, not this runner, routes tools."""
    try:
        from langchain.agents import create_agent
        from langchain.agents.middleware import (ModelCallLimitMiddleware,
                                                  ToolCallLimitMiddleware,
                                                  dynamic_prompt, wrap_model_call)
        from langchain_openrouter import ChatOpenRouter
        from langgraph.checkpoint.memory import InMemorySaver
    except ImportError as exc:
        raise RuntimeError('Install graph dependencies: pip install -r requirements-agent.txt') from exc

    previous = [0.0]
    sequence = [0]
    env.graph_request_limit_active = True

    @wrap_model_call
    def monitor_calls(request, handler):
        env.input_token_budget.before_request()
        sequence[0] += 1
        env.model_requests_started = sequence[0]
        turn = sequence[0]
        env.model_phases[turn] = env.phase
        print(f'    turn={turn}/{MAX_MODEL_CALLS} · provider request ...', flush=True)
        # Keep the user's configured spacing between REAL calls; no silent retries.
        wait = delay - (time.monotonic() - previous[0]) if previous[0] else 0
        if wait > 0:
            time.sleep(wait)
        try:
            response = handler(request)
            env.input_token_budget.after_response(response)
            print(f'    turn={turn}/{MAX_MODEL_CALLS} · provider completed', flush=True)
            return response
        except Exception as exc:
            print(f'    turn={turn}/{MAX_MODEL_CALLS} · provider failed ({type(exc).__name__})', flush=True)
            raise
        finally:
            previous[0] = time.monotonic()

    @dynamic_prompt
    def workflow_prompt(_request):
        # LangChain creates the real dynamic system message on each model call.
        # The model authored the handoff; our immutable instructions remain above it.
        return env.active_system_prompt()

    model = ChatOpenRouter(
        model=model_id, api_key=token, temperature=temperature,
        max_tokens=max_tokens, max_retries=0,
        reasoning={'effort': effort} if effort and effort != 'none' else None,
    )
    return create_agent(
        model=model, tools=make_native_tools(env), system_prompt=agent_prompt(env.task_id),
        middleware=[ModelCallLimitMiddleware(run_limit=MAX_MODEL_CALLS, exit_behavior='end'),
                    ToolCallLimitMiddleware(run_limit=MAX_TOOLS, exit_behavior='end'),
                    workflow_prompt, monitor_calls],
        checkpointer=InMemorySaver(), name='changeimpactbench_agent',
    )


def _as_text(content: Any) -> str:
    return content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, default=str)


def _live_observation(tool: str, result: object) -> object:
    """Keep the evidence needed by the live UI without printing bulky tool payloads."""
    if not isinstance(result, dict):
        return result
    if tool == 'list_repairs':
        candidates = result.get('candidate_repairs')
        if isinstance(candidates, list):
            return {'candidate_repairs': [
                {key: item[key] for key in ('id', 'cost', 'estimated_minutes', 'risk', 'operational_description') if key in item}
                for item in candidates if isinstance(item, dict)
            ]}
    fields = {
        'read_alert': ('alert',),
        'scan_service_health': ('statuses', 'observed_count', 'kind', 'observed_at'),
        'inspect_metrics': ('service', 'health_probe', 'signals', 'freshness', 'measurement_age_seconds'),
        'inspect_config': ('service', 'configuration_snapshot', 'freshness', 'measurement_age_seconds'),
        'inspect_dependencies': ('service', 'upstream', 'direct_consumers'),
        'inspect_logs': ('service', 'lines'),
        'prepare_repair': ('phase', 'handoff_accepted', 'available_simulations'),
        'simulate_repair': ('action_id', 'cost', 'restored_count', 'unavailable_after_count',
                            'newly_unavailable_count', 'simulations_remaining', 'simulated_only'),
        'apply_repair': ('action_id', 'restored_count', 'unavailable_after_count',
                         'newly_unavailable_count', 'committed_in_sandbox'),
        'submit_diagnosis': ('received', 'final_status'),
    }.get(tool)
    if fields is None:
        return result
    return {key: result[key] for key in fields if key in result}


def collect_graph_updates(updates, env: GraphEnvironment, record: dict) -> None:
    """Read-only collector. Stream iteration does NOT implement model/tool routing."""
    for update in updates:
        if not isinstance(update, dict):
            continue
        if 'model' in update:
            node = update['model']
            messages = node.get('messages', []) if isinstance(node, dict) else []
            for message in messages:
                if getattr(message, 'type', None) != 'ai':
                    continue
                # LangChain's model-call limit may synthesize an AIMessage when
                # ending the graph. Do NOT count it as a real provider request.
                if env.graph_request_limit_active and len(record['turns']) >= env.model_requests_started:
                    continue
                turn = len(record['turns']) + 1
                calls = [{'id': x.get('id', ''), 'name': x['name'], 'args': x['args']}
                         for x in (getattr(message, 'tool_calls', []) or [])]
                usage = getattr(message, 'usage_metadata', None) or {}
                metadata = getattr(message, 'response_metadata', None) or {}
                # Provider-exposed content is not private chain of thought.
                exposed = getattr(message, 'additional_kwargs', None) or {}
                # Record only exposed provider summaries; never infer latent thoughts.
                summary = exposed.get('reasoning_details') or exposed.get('reasoning') or None
                entry = {'turn': turn, 'agent_phase': env.model_phases.get(turn, env.phase), 'model_returned': metadata.get('model_name', ''),
                         'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                         'raw_model_output': _as_text(getattr(message, 'content', '')),
                         'tool_calls': calls, 'usage': usage,
                         'finish_reason': metadata.get('finish_reason', ''),
                         'provider_response_id': getattr(message, 'id', None),
                         'provider_exposed_reasoning': summary}
                record['turns'].append(entry)
                record['provider_requests'] = len(record['turns'])
                env.provider_turn = turn
                record['usage']['prompt_tokens'] += int(usage.get('input_tokens') or 0)
                record['usage']['completion_tokens'] += int(usage.get('output_tokens') or 0)
                details = usage.get('output_token_details') or {}
                record['reasoning_tokens'] += int(details.get('reasoning') or 0)
                record['raw_provider_output'] = entry['raw_model_output']
                record['model_returned'] = entry['model_returned'] or record.get('model_returned', '')
                record['finish_reason'] = entry['finish_reason']
                if not calls:
                    print('    protocol error: model ended without invoking a terminal diagnosis', flush=True)
        if 'tools' in update:
            # The tool node already executed under LangGraph. This code reads
            # actual sandbox results rather than calling any tool itself.
            node = update['tools']
            messages = node.get('messages', []) if isinstance(node, dict) else []
            for message in messages:
                if getattr(message, 'type', None) != 'tool':
                    continue
                text = _as_text(getattr(message, 'content', ''))
                try:
                    observed = json.loads(text)
                except ValueError:
                    observed = {'tool_error': text[:300]}
                if isinstance(observed, dict) and 'event_id' in observed:
                    tool = observed['tool']
                    visible = _live_observation(tool, observed.get('result', {}))
                    print(f"    {observed['event_id']} {tool} → {json.dumps(visible, separators=(',', ':'))}", flush=True)
                elif isinstance(observed, dict) and observed.get('rejected'):
                    print(f"    protocol error: {observed.get('reason','rejected')}", flush=True)
                else:
                    print('    protocol error: tool schema or dispatch rejected', flush=True)


def recursion_step_limit(provider_budget: int) -> int:
    """Graph steps are NOT provider calls: middleware creates additional steps.

    A generous recursion ceiling protects a *different* failure mode; actual
    paid/free provider-call and tool budgets remain enforced independently.
    """
    if provider_budget < 1:
        raise ValueError('provider_budget must be positive')
    return max(512, provider_budget * 16 + 64)


def redact_secret(message: str, secret: str) -> str:
    if secret:
        message = message.replace(secret, '[REDACTED-OPENROUTER-KEY]')
    message = re.sub(r'sk-or-v1-[A-Za-z0-9_-]+', '[REDACTED-OPENROUTER-KEY]', message)
    message = re.sub(r'(?i)(authorization\s*[:=]\s*bearer\s+)\S+', r'\1[REDACTED]', message)
    return message


def classify_execution_error(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    detail = str(exc).lower()
    if 'graphrecursionerror' in name or 'recursion limit' in detail:
        return 'graph_recursion_limit'
    if 'ratelimit' in name or '429' in detail or 'rate limit' in detail:
        return 'provider_rate_limit'
    if 'authentication' in name or '401' in detail or 'invalid api key' in detail:
        return 'provider_authentication'
    if 'connection' in name or 'timeout' in name or 'network' in detail:
        return 'provider_network_error'
    if 'api' in name or 'openrouter' in detail or 'provider' in detail:
        return 'provider_api_error'
    return 'framework_orchestration_error'


def run_episode(task_id: str, model: str, trial: int, token: str,
                max_tokens: int, effort: str | None, temperature: float,
                delay: float, graph_factory: Callable | None = None, *,
                max_input_tokens: int = DEFAULT_MAX_INPUT_TOKENS) -> dict:
    """Make exactly one LangGraph invocation for an episode; persist after exit."""
    if task_id not in TASK_IDS:
        raise ValueError(f'Unknown prospective agent task {task_id}')
    prompt = agent_prompt(task_id)
    env = GraphEnvironment(task_id)
    env.input_token_budget = InputTokenBudget(max_input_tokens)
    record = {
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'task_id': task_id, 'benchmark_version': VERSIONS[task_id],
        'agent_framework': ENGINE,
        'grading_contract': contract_for(task_id),
        'model_requested': model, 'trial': trial,
        'temperature_requested': temperature, 'max_tokens_requested': max_tokens,
        'max_input_tokens_requested': max_input_tokens,
        'input_token_budget_policy': 'cumulative provider-reported input tokens per trial; gate before next request',
        'reasoning_effort_requested': effort, 'delay_seconds': delay,
        'prompt': prompt, 'prompt_sha256': hashlib.sha256(prompt.encode()).hexdigest(),
        'case_sha256': digest(source_case(task_id)),
        'source_hashes': recorded_implementation_hashes(task_id),
        'status': 'incomplete_workflow', 'raw_output': '',
        'raw_provider_output': '', 'turns': [], 'trajectory': [],
        'tool_attempts': [], 'provider_requests': 0,
        'final_diagnosis': None, 'committed_effect': None,
        'repair_brief': None, 'repair_system_prompt': None,
        'repair_system_prompt_sha256': None,
        'usage': {'prompt_tokens': 0, 'completion_tokens': 0},
        'reasoning_tokens': 0, 'tool_calls': 0,
        'checkpoint_kind': 'LangGraph in-process checkpointer; JSONL is durable artifact',
        'hidden_reasoning_available': False,
    }
    record['runtime'] = {
        'python': sys.version.split()[0],
        'packages': {},
        'checkpoint': 'LangGraph InMemorySaver (in-process only)',
    }
    for package in ('langchain', 'langgraph', 'langchain-core', 'langchain-openrouter'):
        try:
            record['runtime']['packages'][package] = package_version(package)
        except PackageNotFoundError:
            record['runtime']['packages'][package] = None
    started = time.perf_counter()
    try:
        graph = (graph_factory or build_graph)(env, model, token, max_tokens, effort, temperature, delay)
        # create_agent controls all transitions and tool dispatch, not a manual loop.
        collect_graph_updates(graph.stream(
            {'messages': [{'role': 'user', 'content': 'Investigate a reconstruction based on a public incident report, repair only the offline sandbox, and submit_diagnosis.'}]},
            config={'configurable': {'thread_id': f'{task_id}-{trial}-{int(time.time()*1000)}'},
                    'recursion_limit': recursion_step_limit(MAX_MODEL_CALLS)}, stream_mode='updates',
        ), env, record)
        if any(len(t.get('tool_calls', [])) > 1 for t in record['turns']):
            record['status'] = 'unsupported_tool_protocol'
            print('    protocol error: multiple native tools in one provider response', flush=True)
        elif env.final is not None:
            record['status'] = 'completed'
        elif record['provider_requests'] >= MAX_MODEL_CALLS or len(env.steps) >= MAX_TOOLS:
            record['status'] = 'budget_exhausted'
    except InputTokenBudgetExceeded as exc:
        record['status'] = 'input_budget_exhausted'
        record['termination_reason'] = 'input_token_budget'
        print(f'    {exc}', flush=True)
    except InputTokenUsageUnavailable as exc:
        record['status'] = 'input_usage_unavailable'
        record['termination_reason'] = 'provider_input_usage_missing'
        print(f'    {exc}', flush=True)
    except EpisodeInterrupted:
        record['status'] = 'stopped'
        record['error_category'] = 'user_stopped'
        record['error'] = 'Stopped by user; accepted synthetic effects retained'
    except Exception as exc:
        category = classify_execution_error(exc)
        record['status'] = 'api_error' if category.startswith('provider_') else 'orchestration_error'
        record['error_category'] = category
        record['error_class'] = type(exc).__name__
        trace = redact_secret(''.join(traceback.format_exception(exc)), token)
        record['error'] = redact_secret(f'{type(exc).__name__}: {exc}', token)[:500]
        record['error_traceback_redacted'] = trace[-12000:]
        # No silent catch: the full redacted stack is visible in subprocess
        # logs AND forwarded to the FastAPI terminal by the tee service.
        print(f'    ERROR [{category}] {type(exc).__name__}: {record["error"]}', file=sys.stderr, flush=True)
        print(trace, file=sys.stderr, flush=True)
    finally:
        record['elapsed_seconds'] = round(time.perf_counter() - started, 3)
        record['input_tokens_reported'] = env.input_token_budget.used
        record['input_token_budget_reached'] = env.input_token_budget.used >= max_input_tokens
        record['input_token_usage_available'] = not env.input_token_budget.usage_missing
        record['repair_brief'] = env.repair_brief
        if env.repair_brief is not None:
            record['repair_system_prompt'] = env.active_system_prompt()
            record['repair_system_prompt_sha256'] = hashlib.sha256(record['repair_system_prompt'].encode('utf-8')).hexdigest()
        record['final_diagnosis'] = env.final
        record['committed_effect'] = env.committed_effect
        record['simulations_used'] = env.underlying.simulations
        record['tool_calls'] = len(env.steps)
        record['model_requests_started'] = env.model_requests_started if env.graph_request_limit_active else record['provider_requests']
        record['violations'] = list(env.underlying.violations)
        record['tool_attempts'] = env.attempts
        record['trajectory'] = [dict(a, raw_model_output=json.dumps({'native_tool': a['tool'], 'arguments': a['arguments']}, sort_keys=True),
                                     timestamp_utc=record['turns'][a['provider_turn'] - 1]['timestamp_utc'] if a['provider_turn'] > 0 and a['provider_turn'] <= len(record['turns']) else record['timestamp_utc'])
                                for a in env.attempts if 'observation' in a]
        record['protocol_errors'] = [
            {'turn': a['provider_turn'], 'reason': a['rejected_reason'], 'category': 'rejected_tool_call'}
            for a in env.attempts if a.get('rejected_reason')
        ]
        # Normalized final answer is explicitly derived from the terminal TOOL,
        # never misrepresented as a raw free-text model output.
        record['raw_output'] = json.dumps({'native_terminal_tool': 'submit_diagnosis',
                                           'arguments': env.final}, sort_keys=True) if env.final else (record['raw_provider_output'] or '[no final submission]')
    verification = active_replay_record(record)
    record['replay_verified'] = verification['verified']
    if verification['grade'] is not None:
        record['grade'] = verification['grade']
    if not verification['verified']:
        if record['status'] not in ('input_budget_exhausted', 'input_usage_unavailable'):
            record['status'] = 'unverified'
        record['audit_warnings'] = verification['warnings']
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description='LangChain create_agent / LangGraph tool-use evaluation; synthetic-only')
    parser.add_argument('--models', nargs='+', required=True)
    parser.add_argument('--tasks', nargs='+', required=True)
    parser.add_argument('--trials', type=int, default=1)
    parser.add_argument('--max-tokens', type=int, default=8000)
    parser.add_argument('--max-input-tokens', type=int, default=DEFAULT_MAX_INPUT_TOKENS)
    parser.add_argument('--reasoning-effort', default='low')
    parser.add_argument('--temperature', type=float, default=0)
    parser.add_argument('--delay', type=float, default=3)
    parser.add_argument('--max-requests', type=int, default=MAX_MODEL_CALLS)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if (not 1 <= len(args.models) <= 5 or len(set(args.models)) != len(args.models) or len(args.tasks) != 1 or not 1 <= args.trials <= 5
            or args.tasks[0] not in TASK_IDS or not args.models[0].endswith(':free')
            or args.max_requests != MAX_MODEL_CALLS):
        raise SystemExit('Choose 1–5 free models, one public incident and 1–5 repeated trials; approve provider-call budget')
    if not (512 <= args.max_tokens <= 20000
            and MIN_MAX_INPUT_TOKENS <= args.max_input_tokens <= MAX_MAX_INPUT_TOKENS
            and 0 <= args.temperature <= 1 and 3 <= args.delay <= 30):
        raise SystemExit('Invalid model generation limits')
    token = os.getenv('OPENROUTER_API_KEY', '').strip()
    if not token:
        raise SystemExit('OPENROUTER_API_KEY is missing')
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to((ROOT / 'results').resolve()) or output.suffix != '.jsonl':
        raise SystemExit('Output must be results/*.jsonl')
    previous = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, _stop_signal)
    try:
        total = len(args.models) * args.trials
        for idx, (model, trial) in enumerate(((m,t) for m in args.models for t in range(1,args.trials+1)),1):
            print(f'[{idx}/{total}] LangGraph create_agent · {model} · {args.tasks[0]} · trial={trial}', flush=True)
            record = run_episode(args.tasks[0], model, trial, token, args.max_tokens,
                                 args.reasoning_effort, args.temperature, args.delay,
                                 max_input_tokens=args.max_input_tokens)
            with output.open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
                stream.flush()
            print(f"    score={(record.get('grade') or {}).get('score')} pass={(record.get('grade') or {}).get('pass')} status={record['status']}", flush=True)
        print(f'Run saved: {output}', flush=True)
    finally:
        signal.signal(signal.SIGTERM, previous)


if __name__ == '__main__':
    main()
