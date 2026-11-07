"""Regression test for the real @tool NameError without requiring provider packages.

LangChain's decorator resolves nested function annotations against their
*defining module*. A closure-local InjectedToolCallId import previously failed.
This stub reproduces the introspection used during actual tool schema creation.
"""
from __future__ import annotations

from typing import Annotated, get_args, get_origin, get_type_hints
import unittest
from unittest.mock import patch

from benchmarks import runner


class FakeInjectedToolCallId:
    pass


class NativeToolAnnotationTests(unittest.TestCase):
    def test_all_eleven_native_schemas_have_resolvable_module_level_injection(self):
        names = []

        def fake_tool(fn=None, **opts):
            def decorate(func):
                hints = get_type_hints(func, include_extras=True)
                injected = hints.get('tool_call_id')
                self.assertIs(get_origin(injected), Annotated)
                self.assertIn(FakeInjectedToolCallId, get_args(injected))
                names.append(func.__name__)
                return func
            return decorate(fn) if fn is not None else decorate

        with patch.object(runner, 'tool', fake_tool), patch.object(runner, 'InjectedToolCallId', FakeInjectedToolCallId):
            native = runner.make_native_tools(object())
        self.assertEqual(len(native), 11)
        self.assertEqual(names, [
            'read_alert', 'scan_service_health', 'inspect_metrics', 'inspect_logs',
            'inspect_config', 'inspect_dependencies', 'list_repairs',
            'prepare_repair', 'simulate_repair', 'apply_repair', 'submit_diagnosis',
        ])
