"""Version-scoped empirical model comparisons."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from agent_graph import TASK_IDS as AGENT_TASKS, VERSIONS as GRAPH_VERSIONS
from dashboard_data import audit_record
from api.services.storage import visible_runs, records_for, review_for
from tasks import load_cases

router = APIRouter()


@router.get('/api/agentic/comparison')
def compare_agentic(task_id: str = 'RW01V2'):
    """Cross-run aggregate, with task VERSION and model settings as strict grouping keys."""
    if task_id not in AGENT_TASKS:
        raise HTTPException(400, 'Choose one agentic task version')
    cases = {c['id']: c for c in load_cases()}
    batches: dict[tuple, dict] = {}
    for path in visible_runs():
        try:
            records = records_for(path.name)
        except HTTPException:
            continue
        for index, r in enumerate(records):
            if r.get('task_id') != task_id:
                continue
            key = (r.get('benchmark_version'), r.get('model_requested'),
                   r.get('temperature_requested'), r.get('max_tokens_requested'),
                   r.get('reasoning_effort_requested'))
            item = batches.setdefault(key, {'benchmark_version': key[0], 'model': key[1],
                'temperature': key[2], 'max_tokens': key[3], 'reasoning_effort': key[4],
                'episodes': 0, 'completed': 0, 'strict_passes': 0, 'incomplete_repairs': 0,
                'complete_safe_repairs': 0, 'initial_impact_errors': 0, 'root_cause_errors': 0,
                'repair_selection_errors': 0, 'protocol_error_episodes': 0,
                'unsafe_commits': 0, 'api_errors': 0, 'generation_incomplete': 0,
                'other_non_gradeable': 0, 'unverified': 0, 'human_verified': 0, 'evidence': []})
            item['episodes'] += 1
            a = audit_record(r, cases)
            verified = a['prompt_sha_matches'] is True and a['reference_matches'] is True and a['stored_grade_matches'] is not False
            st = a['status']
            if not verified or st == 'unverified':
                item['unverified'] += 1
                outcome = 'unverified'
            elif st == 'completed' and isinstance(a.get('grade'), dict):
                g = a['grade']
                item['completed'] += 1
                item['strict_passes'] += int(g.get('strict_pass') is True)
                item['incomplete_repairs'] += int(g.get('recovery_safe') is True and g.get('recovery_success') is False)
                item['unsafe_commits'] += int(g.get('unsafe_commit') is True)
                item['complete_safe_repairs'] += int(g.get('recovery_success') is True and g.get('recovery_safe') is True)
                item['initial_impact_errors'] += int(isinstance(g.get('affected_f1'), (float, int)) and g['affected_f1'] < 1)
                item['root_cause_errors'] += int(g.get('root_correct') is False)
                item['repair_selection_errors'] += int(g.get('fix_correct') is False)
                item['protocol_error_episodes'] += int(bool(g.get('protocol_errors')))
                outcome = 'strict_pass' if g.get('strict_pass') is True else ('unsafe_commit' if g.get('unsafe_commit') else 'strict_fail')
            elif st == 'api_error':
                item['api_errors'] += 1
                outcome = 'api_error'
            elif st in ('incomplete_generation', 'empty_generation'):
                item['generation_incomplete'] += 1
                outcome = st
            else:
                item['other_non_gradeable'] += 1
                outcome = st
            note = review_for(path.name, index, r)
            item['human_verified'] += int(note is not None and note['status'] == 'verified')
            item['evidence'].append({'run': path.name, 'index': index, 'status': outcome,
                                     'human_review': note['status'] if note else 'pending'})
    groups = sorted(batches.values(), key=lambda x: (str(x['model']), str(x['reasoning_effort'])))
    for g in groups:
        g['strict_pass_rate_completed'] = (g['strict_passes']/g['completed']) if g['completed'] else None
    return {'task_id': task_id, 'benchmark_version': {
        **GRAPH_VERSIONS}[task_id],
        'groups': groups, 'scope': 'No pooling across task versions or generation settings. Observational aggregate, not a controlled head-to-head study.'}

