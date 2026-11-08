"""Single active scoring policy for NEW runs; preserve legacy replay verbatim.

V4: source-grounded lexical evidence score, provisional until human review.
V6CF: unchanged independently replayed synthetic-outcome grade.
Old records: evaluated with the contract they were originally recorded under.
"""
from __future__ import annotations
from benchmarks.grader import replay_record as replay_sandbox
from benchmarks.grader_source import score_report, report_from_final, action_source_status

SOURCE_CONTRACT = 'source-grader-2-control-room'


def contract_for(task_id: str) -> str:
    return SOURCE_CONTRACT if task_id in {f'RW{i:02d}V4' for i in range(1, 7)} else 'synthetic-replay'


def replay_record(record: dict) -> dict:
    replay = replay_sandbox(record)  # independent provenance / transcript verification ONLY
    if record.get('grading_contract') != SOURCE_CONTRACT:
        return replay  # historical evidence or V6CF: never rewrite stored results
    if not record.get('task_id', '').endswith('V4'):
        result = dict(replay)
        result.update(verified=False, grade=None, warnings=[*replay.get('warnings', []), 'Source contract attached to non-V4 task'])
        return result
    if not replay['verified']:
        return replay
    if record.get('status') != 'completed' or not isinstance(replay.get('predicted'), dict):
        return dict(replay, grade=None)
    final = replay['predicted']
    source = score_report(record['task_id'], report_from_final(final))
    grade = {
        'grading_contract': SOURCE_CONTRACT,
        'score': round(source['final_score'] / 100, 5),
        'pass': None, 'strict_pass': None,
        'source_provisional': True,
        'source_semantics_verified': False,
        'source_score': source,
        'source_url': source['source_url'],
        'committed_action': (replay.get('grade') or {}).get('committed_action'),
        'committed_action_source_status': action_source_status(record['task_id'], (replay.get('grade') or {}).get('committed_action') or ''),
        'recovery_safe': None, 'recovery_success': None, 'root_correct': None,
        'fix_correct': None, 'affected_f1': None,
        'reasons': ['source_lexical_score_requires_human_semantic_review'],
        'warning': 'Historical evidence score is lexical/provisional. Sandbox repair is not historical proof.',
    }
    return dict(replay, grade=grade)
