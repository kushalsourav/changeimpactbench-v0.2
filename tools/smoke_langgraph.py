#!/usr/bin/env python3
"""Compile a real native LangGraph agent and tool schemas OFFLINE; never call a model.

Requires `pip install -r requirements-agent.txt`. Intentionally does NOT run
`.invoke()`, `.stream()`, or call OpenRouter; real native provider compatibility
must be verified separately with an approved live episode.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent_graph import GraphEnvironment
from run_graph_agent import build_graph, make_native_tools


def main() -> int:
    try:
        from langchain.agents import create_agent  # noqa: F401
        from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware, dynamic_prompt  # noqa: F401
        from langchain_openrouter import ChatOpenRouter  # noqa: F401
        from langgraph.checkpoint.memory import InMemorySaver  # noqa: F401
    except ImportError as exc:
        print(f'Native LangGraph dependency missing: {exc}', file=sys.stderr)
        print('Install with: pip install -r requirements-agent.txt', file=sys.stderr)
        return 2
    env = GraphEnvironment('RW01V3')
    tools = make_native_tools(env)
    assert len(tools) == 11, 'Exactly eleven native tools are required'
    for native_tool in tools:
        schema = native_tool.tool_call_schema.model_json_schema()
        assert 'tool_call_id' not in schema.get('properties', {}), (
            f'{native_tool.name}: injected tool ID leaked into model-visible arguments'
        )
    # A placeholder is ONLY supplied to instantiate the model class; no API call.
    graph = build_graph(env, 'nvidia/nemotron-3-ultra-550b-a55b:free',
                        'offline-placeholder-key', 1024, 'low', 0, 3)
    initial_prompt = env.active_system_prompt()
    assert 'incident investigation skill' in initial_prompt.lower()
    nodes = list(graph.get_graph().nodes)
    assert 'model' in nodes and 'tools' in nodes, nodes
    print(json.dumps({'compiled_native_agent': True, 'model_invoked': False,
                      'real_provider_calls': 0, 'native_tools': [t.name for t in tools],
                      'graph_nodes': nodes, 'sandbox': 'postmortem-grounded reconstruction; no production access'}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
