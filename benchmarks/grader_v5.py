"""Additive, versioned evidence-category audit for frozen V4 episode records.

V4 canonical score and hash-bound implementation remain unchanged. This module
produces a separately labeled V5 evidence-category re-evaluation after full
independent V4 replay. It does NOT grade semantic truth of explanations.
"""
from __future__ import annotations

from copy import deepcopy
from benchmarks.grader import replay_record

V5_AUDIT_CONTRACT = 'v5-evidence-category-audit-1'
QUALIFYING_TOOLS = frozenset({
    'scan_service_health', 'inspect_config', 'inspect_dependencies',
    'inspect_logs', 'inspect_metrics', 'simulate_repair',
})


def audit_v5(record: dict) -> dict:
    """Compute a V5 evidence-category verdict without overwriting historical V4 grade."""
    if not str(record.get('task_id', '')).endswith('V4'):
        raise ValueError('V5 audit currently supports frozen V4 agentic records only')
    replay = replay_record(record)
    if not replay['verified'] or replay['grade'] is None:
        return {'contract': V5_AUDIT_CONTRACT, 'verified': False,
                'warnings': replay.get('warnings', []), 'grade': None}

    historical = replay['grade']  # independent deterministic V4 result
    final = replay['predicted']
    citation_ids = set(final['evidence_ids'])
    observations = {
        event['observation']['event_id']: event['tool']
        for event in record['trajectory']
    }  # independently replay-validated above; no cached grades trusted
    existing = citation_ids & observations.keys()
    missing = sorted(citation_ids - observations.keys())
    qualifying = sorted(x for x in existing if observations[x] in QUALIFYING_TOOLS)
    provenance_complete = not missing and len(citation_ids) >= 2
    evidence_score = 10 if provenance_complete and len(qualifying) >= 2 else (
        5 if provenance_complete and qualifying else 0
    )

    grade = deepcopy(historical)
    old_evidence = grade['evidence_score']
    grade['evidence_score'] = evidence_score
    grade['criterion_scores']['evidence_provenance'] = {
        'earned': evidence_score,
        'available': 10,
        'measurement': 'observed event IDs; dependency inspections qualify; no semantic entailment',
    }
    grade['score'] = round(grade['score'] + (evidence_score - old_evidence) / 100, 5)
    # The original independent replay checked diagnosis, repair, safety,
    # protocol and all other strict criteria. Only evidence class changes.
    non_evidence_failures = [
        reason for reason in historical['strict_failure_reasons']
        if reason != 'insufficient_evidence_provenance'
    ]
    reasons = non_evidence_failures + (
        ['insufficient_evidence_provenance'] if evidence_score != 10 else []
    )
    grade['strict_failure_reasons'] = reasons
    grade['strict_pass'] = grade['pass'] = not reasons
    grade['pass_contract'] = V5_AUDIT_CONTRACT
    grade['evidence_review'] = 'provenance and evidence-type audit only; human semantic review pending'
    return {
        'contract': V5_AUDIT_CONTRACT,
        'verified': True,
        'task_id': record['task_id'],
        'warnings': [],
        'historical_v4_grade': historical,
        'grade': grade,
        'citation_audit': {
            'cited_event_count': len(citation_ids),
            'missing_event_ids': missing,
            'qualifying_event_ids': qualifying,
            'qualifying_types': sorted({observations[x] for x in qualifying}),
            'human_semantic_review_required': True,
        },
        'grading_change': 'inspect_dependencies added to V4 qualifying evidence categories',
    }
