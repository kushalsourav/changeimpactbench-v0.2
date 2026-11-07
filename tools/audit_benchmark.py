#!/usr/bin/env python3
"""Local deterministic audit. This does NOT simulate or claim provider outcomes."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from benchmarks.spec import REGISTRY, reference_trajectory, source_case
from agent_graph import GraphEnvironment, TASK_IDS, VERSIONS
from dashboard_data import available_runs, audit_record, parse_jsonl
from oracle import initial_failures, reference_answer, reference_audit, simulate
from tasks import load_cases


def run_audit(root:Path=ROOT)->dict:
    cases=load_cases()
    report={'generated_utc':datetime.now(timezone.utc).isoformat(),
            'scope':'Offline synthetic oracle verification and source-bound raw native tool replay. No LLM trial is fabricated.',
            'seed_tasks':[], 'agentic_tasks':[], 'recorded_episodes':[], 'archived_episodes':[], 'warnings':[]}
    for case in cases:
        reference=reference_answer(case)
        failures,_=simulate(case)
        direct,_=initial_failures(case['id'],case['facts'])
        outcomes=reference_audit(case)['actions']
        best=min((a['cost'] for a in case['actions'] if outcomes[a['id']]['full_recovery']),default=None)
        actual_action=next((a for a in case['actions'] if a['id']==reference['fix_id']), None)
        ref_file=root/'reference'/f"{case['id']}.json"
        saved=json.loads(ref_file.read_text(encoding='utf-8')) if ref_file.exists() else None
        passed=bool(actual_action and best is not None and actual_action['cost']==best
                    and sorted(failures)==reference['failed_services'] and saved==reference and direct)
        report['seed_tasks'].append({'task':case['id'],'services':len(case['facts']['topology']),
            'initial_outages':len(failures),'initial_local_faults':sorted(direct),
            'least_cost_complete_safe_repair':reference['fix_id'],
            'oracle_matches_stored_reference':saved==reference,'offline_checks_pass':passed})
    for task_id in sorted(TASK_IDS):
        env=GraphEnvironment(task_id)
        trajectory=reference_trajectory(task_id)
        for i,(tool,args) in enumerate(trajectory,1):
            env.provider_turn=i
            result=json.loads(env.execute(tool,args,f'offline-reference-{i}'))
            assert not result.get('rejected'), (task_id,tool,result)
        reference=reference_answer(source_case(task_id))
        passed=bool(env.final and env.committed_effect and
                    set(env.final['failed_services'])==set(reference['failed_services']) and
                    env.final['root_cause_id']==reference['root_cause'] and
                    env.underlying.committed==reference['fix_id'] and
                    not env.committed_effect['unavailable_after'] and
                    not env.committed_effect['newly_unavailable'])
        report['agentic_tasks'].append({'task':task_id,'version':VERSIONS[task_id],
            'seed':REGISTRY[task_id].seed,'reference_tool_calls':len(trajectory),
            'reference_submission_correct':passed,'is_real_model_trial':False,
            'human_semantic_review':'pending'})
    for path in available_runs(root):
        try:
            records=parse_jsonl(path.read_text(encoding='utf-8'))
        except (OSError,ValueError) as exc:
            report['warnings'].append(f'{path.name}: invalid JSONL ({type(exc).__name__})')
            continue
        for index,rec in enumerate(records):
            if rec.get('task_id') not in TASK_IDS:
                report['archived_episodes'].append({'file':path.name, 'index':index,
                    'task_id':rec.get('task_id'), 'stored_grade_only':rec.get('grade'),
                    'note':'Historical contract: not regraded or pooled under v2'})
                continue
            review=audit_record(rec)
            report['recorded_episodes'].append({'file':path.name,'index':index,
                'task_id':rec.get('task_id'),'model':rec.get('model_requested'),
                'status':review['status'],'prompt_verified':review['prompt_sha_matches'],
                'oracle_verified':review['reference_matches'],
                'grade_matches_replay':review['stored_grade_matches'],
                'strict_pass':(review.get('grade') or {}).get('strict_pass'),
                'warnings':review['warnings'],'human_review':'not automatically verified'})
    report['all_offline_checks_pass']=all(x['offline_checks_pass'] for x in report['seed_tasks']) and all(
        x['reference_submission_correct'] for x in report['agentic_tasks'])
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path, default=ROOT/'reports/offline_audit.json')
    args=p.parse_args()
    report=run_audit()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'seed_oracles':len(report['seed_tasks']),'native_reference_trajectories':len(report['agentic_tasks']),
        'real_saved_episodes':len(report['recorded_episodes']),
        'all_offline_checks_pass':report['all_offline_checks_pass']},indent=2))
    if not report['all_offline_checks_pass']:
        raise SystemExit(1)

if __name__=='__main__':main()
