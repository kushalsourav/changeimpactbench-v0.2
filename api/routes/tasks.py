"""Synthetic task catalog and reviewer-only reference detail."""
from __future__ import annotations
import json
from fastapi import APIRouter, HTTPException
from agent_graph import TASK_IDS as GRAPH_TASKS, VERSIONS as GRAPH_VERSIONS, agent_prompt as graph_prompt, source_case as graph_case, task_catalog as graph_catalog
from oracle import reference_answer, reference_audit, initial_failures, patch_facts

router = APIRouter()


@router.get('/api/tasks')
def tasks():
    return [graph_catalog(task_id) for task_id in sorted(GRAPH_TASKS)]


@router.get('/api/tasks/{task_id}')
def task_info(task_id: str):
    """Reviewer reference endpoint; the agent sees only native bounded tools."""
    if task_id not in GRAPH_TASKS:
        raise HTTPException(404, 'Unknown active agentic task')
    original = graph_case(task_id)
    case = json.loads(json.dumps(original))
    case['id'] = task_id
    case['benchmark_version'] = GRAPH_VERSIONS[task_id]
    audit = reference_audit(original)
    for action in original['actions']:
        patched = patch_facts(original['facts'], action)
        direct_after, _ = initial_failures(original['id'], patched)
        audit['actions'][action['id']]['direct_failed_after'] = sorted(direct_after)
    direct_before, _ = initial_failures(original['id'], original['facts'])
    return {'case':case, 'prompt':graph_prompt(task_id),
            'reference':reference_answer(original),
            'direct_failed_services':sorted(direct_before),'audit':audit,
            'condition':'agentic', 'reference_visible_to_agent':False}

