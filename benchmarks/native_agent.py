"""Prospective native LangGraph agent evaluator; synthetic sandbox and independent replay.

The active evaluation has no home-grown model/tool loop. LangChain create_agent
orchestrates tool use; this module provides versioned conditions, native tool
tracking and independently verified grading. No real infrastructure access.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from threading import RLock
from typing import Any

from benchmarks.environment import AgentEnvironment, ProtocolError
from benchmarks.skills import skill_hashes, repair_system_prompt
from benchmarks.spec import V6_REGISTRY, digest, get_spec, source_case, service_codes, synthetic_task, reviewer_source
from oracle import reference_answer, reference_audit

# No V4, V5 or V6-neutral task IDs can be launched or replayed as current tasks.
GRAPH_BASE: dict[str, str] = {name: spec.seed for name, spec in V6_REGISTRY.items()}
TASK_IDS = ACTIVE_TASK_IDS = frozenset(GRAPH_BASE)
VERSIONS = {name: spec.version for name, spec in V6_REGISTRY.items()}
MAX_MODEL_CALLS = 48
MAX_TOOLS = 47
MAX_SIMULATIONS = 5
TOOL_NAMES = frozenset({
    'read_alert', 'scan_service_health', 'inspect_metrics', 'inspect_logs',
    'inspect_config', 'inspect_dependencies', 'list_repairs',
    'prepare_repair', 'simulate_repair', 'apply_repair', 'submit_diagnosis',
})

ENGINE = 'langchain-create-agent/langgraph-checkpointed'


def implementation_hashes() -> dict[str, str]:
    """Hash only the files needed to execute and deterministically verify V6CF.

    Frozen transcripts made with a different set of hashes must be marked
    unverified, not silently regraded under new source code.
    """
    root = Path(__file__).resolve().parent.parent
    names = (
        'benchmarks/native_agent.py', 'benchmarks/runner.py',
        'benchmarks/grader.py', 'benchmarks/grading_policy.py',
        'benchmarks/spec.py', 'benchmarks/environment.py',
        'benchmarks/skills.py',
        'agent_graph.py', 'run_graph_agent.py', 'oracle.py',
        'skills/incident-investigation/SKILL.md',
        'skills/repair-verification/SKILL.md',
        'skills/repair-verification/V6.md',
    )
    names += tuple(f'benchmarks/v6_fixtures/counterfactual/RW{i:02d}.json' for i in range(1, 7))
    names += tuple(f'reference/v6-counterfactual/RW{i:02d}.json' for i in range(1, 7))
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def recorded_implementation_hashes(task_id: str, recorded: dict[str, str] | None = None) -> dict[str, str]:
    """Require the exact current V6CF implementation for independent replay."""
    if task_id not in ACTIVE_TASK_IDS:
        raise ValueError('Only current V6 counterfactual tasks can be replayed')
    return implementation_hashes()


def task_catalog(task_id: str) -> dict:
    case = source_case(task_id)
    provenance = reviewer_source(task_id)
    title = provenance['original_source_name']
    return {
        'id': task_id, 'title': title + ' · V6 counterfactual',
        'dataset_name': title, 'original_source_name': title,
        'alert': get_spec(task_id).alert,
        'dataset_origin': 'synthetic counterfactual (inspired by public postmortem)',
        'source_seed': get_spec(task_id).seed,
        'context': provenance['attribution_note'],
        'source_url': provenance['source_url'],
        'documented_facts': provenance['documented_facts'],
        'model_assumptions': provenance['reconstructed_elements'],
        'services': len(case['facts']['topology']),
        'failed': len(reference_answer(case)['failed_services']),
        'benchmark_version': VERSIONS[task_id], 'condition': 'agentic',
        'agent_framework': ENGINE,
    }


def agent_prompt(task_id: str) -> str:
    """Exactly the public task/instructions; no oracle, local rule values or repair answers."""
    if task_id not in GRAPH_BASE:
        raise ValueError(task_id)
    spec = get_spec(task_id)
    case = source_case(task_id)
    content = {
        'scenario': task_id, 'version': VERSIONS[task_id],
        'source_type': 'Fully synthetic incident sandbox; not live production telemetry',
        'initial_alert': spec.alert,
        'service_inventory': sorted(service_codes(task_id).values()),
        'diagnosis_contract': {
            'root_cause_id': 'REQUIRED: exactly one hypothesis ID from the supplied list; do NOT put explanatory prose in this field',
            'root_cause_explanation': 'REQUIRED: explain the causal mechanism in your own words, referencing inspected observations; human semantic review is separate from ID scoring',
            'evidence_ids': 'Cite only observed EV identifiers; citations are checked for existence, not automatically semantic truth',
        },
        'objective': ('Identify EXACTLY the initially unavailable services and the interacting local causes; '
                      'commit ONE lowest-cost repair that restores every initially unavailable service '
                      'and creates ZERO new outages. Partial recovery is a failure. '
                      'Submit a diagnosis with actual evidence IDs and the initial, not repaired, impact set.'),
        'rules': [
            'All service incidents and repairs are synthetic, with no access to real infrastructure.',
            'Use native tool calls, not JSON-only messages; issue only ONE tool call per model response.',
            'Call read_alert and scan_service_health early. The scan reports external entrypoint probes only. Independently establish the entire initial impact inventory, and prioritize necessary configuration, dependency, and repair checks within the fixed tool budget.',
            'Local checks use declarative eq/ne/gt/ge/lt/le and all/any/not; investigate their actual values.',
            'A service fails if a local check fails, any needs_all dependency fails, all nonempty needs_any fail, or a needs_at_least quorum fails.',
            'Inspect configuration/dependencies to establish causes; local details are one service at a time.',
            'After list_repairs and evidence collection, call prepare_repair with YOUR OWN evidence-based repair instructions, hypothesis ID, initial impact inventory and observed evidence IDs.',
            'This changes the active skill from investigation to repair. The handoff is model-authored and unverified, not oracle ground truth or permission to override sandbox rules.',
            f'Only after prepare_repair may you simulate, commit and submit. Simulations are read-only, up to {spec.max_simulations} accepted attempts.',
            'You may apply ONE repair. Always inspect simulation effects and reject incomplete or harmful options.',
            'Call submit_diagnosis AFTER apply_repair. It is a terminal tool; do not simply answer in prose.',
            'In submit_diagnosis, root_cause_id MUST be one hypothesis ID exactly (e.g. H01), while root_cause_explanation holds the causal description; a description is NOT an ID.',
            'The cause ID is graded exactly. Explanation semantics are not automatically scored; they require separate evidence-based human review.',
            'Evidence IDs are observed tool-event identifiers. Do not cite invented events.',
            f'Budget: at most {spec.max_model_calls} model requests and {spec.max_tools} successful sandbox tools.',
        ],
        'hypotheses': [{'id': x, 'description': y} for x, y in spec.hypotheses],
        'service_mapping': 'read_alert lists opaque service codes only. Recover relationships by inspecting individual services. Health scan covers external probes only; full internal impact requires investigation.',
    }
    content['evaluation_contract'] = ('Strict pass assesses initial impact, cause, safe complete lowest-cost repair, and provenance. '
        'Rejected tool requests reduce procedural score but do not alone fail the episode. Unsafe commits fail.')
    return json.dumps(content, indent=2, sort_keys=True)


class GraphEnvironment:
    """Native tool-call collector around one versioned, synthetic sandbox.

    This adapter never chooses actions for the agent. LangGraph owns model/tool
    routing. The independent replay re-executes submitted native calls.
    """
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.spec = get_spec(task_id)
        self.underlying = AgentEnvironment(self.spec, source_case(task_id))
        self.lock = RLock()
        self.attempts: list[dict] = []
        self.provider_turn = 0
        self.graph_request_limit_active = False
        self.model_requests_started = 0
        self.model_phases: dict[int, str] = {}

    @property
    def repair_brief(self) -> dict | None:
        return self.underlying.repair_brief

    @property
    def phase(self) -> str:
        return 'repair' if self.repair_brief is not None else 'investigation'

    def active_system_prompt(self) -> str:
        return repair_system_prompt(agent_prompt(self.task_id), self.repair_brief)

    @property
    def steps(self) -> list[dict]:
        return self.underlying.steps

    @property
    def final(self) -> dict | None:
        return self.underlying.final

    @property
    def committed_effect(self) -> dict | None:
        return self.underlying.committed_effect

    def execute(self, name: str, args: dict, tool_call_id: str = '') -> str:
        """Run a single sandbox command, recording accepted and rejected calls."""
        with self.lock:
            entry = {'provider_turn': self.provider_turn, 'tool_call_id': tool_call_id,
                     'tool': name, 'arguments': deepcopy(args)}
            try:
                if name not in TOOL_NAMES:
                    raise ProtocolError(f'Unknown native tool {name}')
                observation = self.underlying.execute(name, args)
            except ProtocolError as exc:
                entry['rejected_reason'] = str(exc)
                self.attempts.append(entry)
                return json.dumps({'rejected': True, 'reason': str(exc)}, sort_keys=True)
            entry['observation'] = deepcopy(observation)
            self.attempts.append(entry)
            return json.dumps(observation, sort_keys=True)


