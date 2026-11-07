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
from benchmarks.spec import REGISTRY, TaskSpec, digest, get_spec, source_case
from oracle import reference_answer, reference_audit

# New IDs make the change of agent harness AND discovery affordances explicit.
GRAPH_BASE: dict[str, str] = {name: spec.seed for name, spec in REGISTRY.items()}
TASK_IDS = frozenset(GRAPH_BASE)
VERSIONS = {name: spec.version for name, spec in REGISTRY.items()}
MAX_MODEL_CALLS = 48
MAX_TOOLS = 47
MAX_SIMULATIONS = 3
TOOL_NAMES = frozenset({
    'read_alert', 'scan_service_health', 'inspect_metrics', 'inspect_logs',
    'inspect_config', 'inspect_dependencies', 'list_repairs',
    'prepare_repair', 'simulate_repair', 'apply_repair', 'submit_diagnosis',
})

ENGINE = 'langchain-create-agent/langgraph-checkpointed'


def implementation_hashes() -> dict[str, str]:
    root = Path(__file__).resolve().parent.parent
    names = ('benchmarks/native_agent.py', 'benchmarks/runner.py',
             'benchmarks/grader.py', 'benchmarks/spec.py', 'benchmarks/environment.py',
             'agent_graph.py', 'run_graph_agent.py', 'oracle.py',
             'benchmarks/public_sources.json',
             'benchmarks/skills.py', 'skills/incident-investigation/SKILL.md',
             'skills/repair-verification/SKILL.md')
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in names}


def recorded_implementation_hashes(task_id: str, recorded: dict[str, str] | None = None) -> dict[str, str]:
    """Validate V3 against archived original bytes; V4 against current source."""
    if task_id.endswith('V3'):
        archive = Path(__file__).resolve().parent.parent / 'legacy' / 'v0.9.11'
        expected = json.loads((archive / 'source_hashes.json').read_text())
        actual = {name: hashlib.sha256((archive / name).read_bytes()).hexdigest() for name in expected}
        if actual != expected:
            raise ValueError('Archived v0.9.11 source bytes have changed')
        return expected
    # V4 runs created before the six-task expansion remain independently
    # verifiable against the exact, immutable v0.9.19 benchmark source snapshot.
    # This is not an exemption from hashing: every archived byte is checked.
    if task_id in ('RW01V4', 'RW02V4', 'RW03V4') and recorded is not None:
        archive = Path(__file__).resolve().parent.parent / 'legacy' / 'v0.9.19'
        expected = json.loads((archive / 'source_hashes.json').read_text())
        if recorded == expected:
            actual = {name: hashlib.sha256((archive / name).read_bytes()).hexdigest()
                      for name in expected}
            if actual != expected:
                raise ValueError('Archived v0.9.19 source bytes have changed')
            return expected
    return implementation_hashes()


def task_catalog(task_id: str) -> dict:
    case = source_case(task_id)
    return {
        'id': task_id, 'title': 'Incident response · ' + case['title'],
        'alert': get_spec(task_id).alert,
        'dataset_name': case['title'], 'dataset_origin': 'public incident postmortem / reconstructed sandbox',
        'source_seed': case['id'], 'context': 'Real published outage; simplified modeled sandbox and independently replayable tools.',
        'source_url': get_spec(task_id).source_url,
        'documented_facts': list(get_spec(task_id).documented_facts),
        'model_assumptions': list(get_spec(task_id).model_assumptions),
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
        'source_type': 'Reconstructed sandbox inspired by an operator-published incident, not actual production telemetry',
        'incident_name': case['title'],
        'initial_alert': spec.alert,
        'service_inventory': sorted(n['id'] for n in case['facts']['topology']),
        'diagnosis_contract': {
            'root_cause_id': 'REQUIRED: exactly one hypothesis ID from the supplied H01-H05 list; do NOT put explanatory prose in this field',
            'root_cause_explanation': 'REQUIRED: explain the causal mechanism in your own words, referencing inspected observations; human semantic review is separate from ID scoring',
            'evidence_ids': 'Cite only observed EV identifiers; citations are checked for existence, not automatically semantic truth',
        },
        'objective': ('Identify EXACTLY the initially unavailable services and the interacting local causes; '
                      'commit ONE lowest-cost repair that restores every initially unavailable service '
                      'and creates ZERO new outages. Partial recovery is a failure. '
                      'Submit a diagnosis with actual evidence IDs and the initial, not repaired, impact set.'),
        'rules': [
            'Incident mechanisms are documented by the source, but service states/rules/repair costs are reconstructed; no tool accesses live infrastructure.',
            'Use native tool calls, not JSON-only messages; issue only ONE tool call per model response.',
            'Call read_alert and scan_service_health early. The health scan is a complete INITIAL snapshot but does not reveal causes or repairs.',
            'Local checks use declarative eq/ne/gt/ge/lt/le and all/any/not; investigate their actual values.',
            'A service fails if a local check fails, any needs_all dependency fails, all nonempty needs_any fail, or a needs_at_least quorum fails.',
            'Inspect configuration/dependencies to establish causes; local details are one service at a time.',
            'After list_repairs and evidence collection, call prepare_repair with YOUR OWN evidence-based repair instructions, hypothesis ID, initial impact inventory and observed evidence IDs.',
            'This changes the active skill from investigation to repair. The handoff is model-authored and unverified, not oracle ground truth or permission to override sandbox rules.',
            'Only after prepare_repair may you simulate, commit and submit. Simulations are optional and read-only, up to 3 accepted attempts.',
            'You may apply ONE repair. Always inspect simulation effects and reject incomplete or harmful options.',
            'Call submit_diagnosis AFTER apply_repair. It is a terminal tool; do not simply answer in prose.',
            'In submit_diagnosis, root_cause_id MUST be one hypothesis ID exactly (e.g. H01), while root_cause_explanation holds the causal description; a description is NOT an ID.',
            'The cause ID is graded exactly. Explanation semantics are not automatically scored; they require separate evidence-based human review.',
            'Evidence IDs are observed tool-event identifiers. Do not cite invented events.',
            f'Budget: at most {spec.max_model_calls} model requests and {spec.max_tools} successful sandbox tools.',
        ],
        'hypotheses': [{'id': x, 'description': y} for x, y in spec.hypotheses],
    }
    if task_id.endswith('V4'):
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


