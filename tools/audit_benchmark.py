#!/usr/bin/env python3
"""Deterministic release/reviewer audit. No API calls and no fabricated model data.

Checks every frozen synthetic seed against its reference and enumerates repairs.
Audits any real JSONL files already in results/ using the existing raw-turn replay.
Human semantic review and production realism can NEVER be certified automatically.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agentic_suite import TASK_IDS, SPECS, reference_trajectory, AgentEnvironment
from dashboard_data import audit_record, available_runs, parse_jsonl
from oracle import initial_failures, reference_answer, reference_audit, simulate
from tasks import load_cases


def _semantic_flags(record: dict) -> list[str]:
    flags: list[str] = []
    final = record.get('final_diagnosis') or {}
    if not isinstance(final, dict):
        return flags
    rationale = str(final.get('rationale', ''))
    for match in re.finditer(r'([a-z][\w.]*)\s*=\s*(-?\d+(?:\.\d+)?)\s*(>=|<=|>|<|==)\s*([a-z][\w.]*)\s*=\s*(-?\d+(?:\.\d+)?)', rationale, re.I):
        x, y, op = float(match[2]), float(match[5]), match[3]
        true = {'>':lambda:x>y,'<':lambda:x<y,'>=':lambda:x>=y,
                '<=':lambda:x<=y,'==':lambda:x==y}[op]()
        if not true:
            flags.append('False arithmetic assertion in model rationale: ' + match[0])
    commits = [v for v in record.get('trajectory', []) if v.get('tool') == 'apply_repair']
    if commits:
        commit_turn = commits[0].get('provider_turn', 10**6)
        cited = set(final.get('evidence_ids', []))
        late = [v.get('observation',{}).get('event_id') for v in record.get('trajectory', [])
                if v.get('provider_turn',0) > commit_turn and v.get('tool') in
                ('inspect_config','inspect_logs','inspect_metrics','inspect_dependencies')
                and v.get('observation',{}).get('event_id') in cited]
        if late:
            flags.append('Post-repair inspections cited as evidence: '+', '.join(late))
    return flags


def run_audit(root: Path = ROOT) -> dict:
    cases = load_cases()
    report: dict = {
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Deterministic synthetic-oracle checks, source-aligned raw-transcript replay; human semantic review NOT automated',
        'seed_tasks': [], 'agentic_tasks': [], 'recorded_episodes': [], 'warnings': [],
    }
    case_map = {c['id']:c for c in cases}
    for case in cases:
        task_id = case['id']
        reference = reference_answer(case)
        failures, _ = simulate(case)
        direct, _ = initial_failures(task_id,case['facts'])
        audit = reference_audit(case)['actions']
        complete = [a for a in case['actions'] if audit[a['id']]['full_recovery']]
        lowest = min((a['cost'] for a in complete),default=None)
        ref_action = next((a for a in case['actions'] if a['id']==reference['fix_id']), None)
        expected_path = root/'reference'/f'{task_id}.json'
        stored = json.loads(expected_path.read_text(encoding='utf-8')) if expected_path.exists() else None
        passed = (sorted(failures)==reference['failed_services'] and stored==reference
                  and ref_action is not None and lowest is not None
                  and ref_action['cost']==lowest and audit[reference['fix_id']]['full_recovery']
                  and len(direct)>0)
        report['seed_tasks'].append({
            'task':task_id,'version':case.get('benchmark_version'),
            'services':len(case['facts']['topology']), 'initial_outages':len(failures),
            'direct_local_faults':sorted(direct),
            'oracle_matches_stored_reference':stored==reference,
            'lowest_cost_complete_safe_action':reference['fix_id'],
            'optimum_cost':lowest,'all_candidate_effects':audit,
            'offline_checks_pass':bool(passed),
        })
    for task_id in sorted(TASK_IDS):
        env = AgentEnvironment(task_id)
        steps = reference_trajectory(task_id)
        for tool,args in steps:
            env.execute(tool,args)
        reference = reference_answer(next(c for c in cases if c['id']==SPECS[task_id]['seed']))
        report['agentic_tasks'].append({
            'task':task_id, 'version':SPECS[task_id]['version'], 'seed':SPECS[task_id]['seed'],
            'reference_tool_calls':len(steps),
            'reference_submission_correct':env.final is not None and
            set(env.final['failed_services'])==set(reference['failed_services']) and
            env.final['root_cause']==reference['root_cause'] and
            env.committed==reference['fix_id'] and not env.committed_effect['unavailable_after'] and
            not env.committed_effect['newly_unavailable'],
            'human_review':'pending',
            'live_model_trials':'not included in code release',
        })
    report['agentic_tasks'].insert(0, {
        'task':'AG08V3','version':'agentic-ag08-v3','seed':'T08',
        'reference_tool_calls':9,
        'historical_grader_caveat':'Strict calculation checks safe complete recovery, but omits explicit lowest-cost/reference-action equality. Historical results must not be silently regraded. Human review required.',
        'human_review':'pending',
    })
    for path in available_runs(root):
        try:
            records = parse_jsonl(path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            report['warnings'].append(f'{path.name}: unreadable JSONL: {type(exc).__name__}')
            continue
        for index, rec in enumerate(records):
            audit = audit_record(rec,case_map)
            is_verified = audit['prompt_sha_matches'] is True and audit['reference_matches'] is True and audit['stored_grade_matches'] is not False
            report['recorded_episodes'].append({
                'file':path.name,'index':index,'task_id':rec.get('task_id'),
                'model_id':rec.get('model_requested'),
                'timestamp_utc':rec.get('timestamp_utc'),
                'status':audit['status'],'grade_verified':is_verified,
                'strict_pass':(audit.get('grade') or {}).get('strict_pass', (audit.get('grade') or {}).get('pass')),
                'score':(audit.get('grade') or {}).get('score'),
                'audit_warnings':audit.get('warnings',[]),
                'semantic_review_flags':_semantic_flags(rec),
                'human_semantic_review':'pending unless separately documented in a hash-bound sidecar',
            })
    report['counts'] = {
        'seed_cases':len(report['seed_tasks']),
        'seed_checks_pass':sum(r['offline_checks_pass'] for r in report['seed_tasks']),
        'new_agentic_reference_checks_pass':sum(r.get('reference_submission_correct') is True for r in report['agentic_tasks']),
        'real_provider_episodes_present':len(report['recorded_episodes']),
        'verified_records':sum(x['grade_verified'] for x in report['recorded_episodes']),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=None, help='Write full audit JSON')
    args = parser.parse_args()
    report=run_audit()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n', encoding='utf-8')
    print(json.dumps({'counts':report['counts'],
                      'warnings':report['warnings'],
                      'historical_v3_cost_check':'human adjudication required',
                      'output_file':str(args.output) if args.output else None},indent=2))
    if report['counts']['seed_checks_pass'] != report['counts']['seed_cases'] or \
       report['counts']['new_agentic_reference_checks_pass'] != len(TASK_IDS):
        sys.exit(1)

if __name__=='__main__':main()
