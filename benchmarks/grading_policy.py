"""Only active grader: independent deterministic V6-counterfactual replay."""
from __future__ import annotations
from benchmarks.grader import replay_record


def contract_for(task_id: str) -> str:
    from benchmarks.native_agent import ACTIVE_TASK_IDS
    if task_id not in ACTIVE_TASK_IDS:
        raise ValueError('Only V6 counterfactual is supported')
    return 'synthetic-replay'
