#!/usr/bin/env python3
"""Create native LangChain tool schemas and compile a LangGraph; NO external requests."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from realbench.core import case_for,available
from realbench.runner import NativeEnvironment,make_tools,build_graph
for id in available():
    env=NativeEnvironment(case_for(id))
    tools=make_tools(env)
    assert len(tools)==7
    print(id, 'native schemas:', ', '.join(t.name for t in tools))
# Uses a placeholder key only to construct the ChatOpenRouter model object.
# No graph.invoke() or .stream() is called: NO provider request occurs.
env=NativeEnvironment(case_for(available()[0]))
graph=build_graph(env,'nvidia/nemotron-3-ultra-550b-a55b:free',
                  'TEST_PLACEHOLDER_NOT_A_REAL_KEY',8000,'low',0.0,4.0)
assert hasattr(graph,'stream')
print('LangChain create_agent / LangGraph graph compiled without provider requests.')
