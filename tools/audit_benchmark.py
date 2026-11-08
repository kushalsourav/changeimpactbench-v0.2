#!/usr/bin/env python3
"""Offline V6CF oracle/reference/trajectory audit. Never represents a model trial."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from agent_graph import GraphEnvironment, ACTIVE_TASK_IDS, VERSIONS
from benchmarks.spec import reference_trajectory, source_case, reference_path, service_codes, public_action_ids
from oracle import reference_answer, reference_audit, initial_failures, simulate, patch_facts


def run_audit() -> dict:
    rows = []
    for task_id in sorted(ACTIVE_TASK_IDS):
        case = source_case(task_id)
        reference = reference_answer(case)
        stored = json.loads(reference_path(task_id).read_text(encoding='utf-8'))
        initially_down, _ = simulate(case)
        audits = reference_audit(case)['actions']
        viable = sorted((a['cost'], a['id']) for a in case['actions'] if audits[a['id']]['full_recovery'])
        cheapest_unsafe = next(a for a in case['actions'] if a['id'] == 'A90')
        harmful, _ = simulate(case, patch_facts(case['facts'], cheapest_unsafe))
        env = GraphEnvironment(task_id)
        trajectory = reference_trajectory(task_id)
        expected_public_fix = public_action_ids(task_id)[reference['fix_id']]
        rejects = []
        for i,(tool,args) in enumerate(trajectory,1):
            env.provider_turn = i
            result = json.loads(env.execute(tool, args, f'offline-reference-{i}'))
            if result.get('rejected'):
                rejects.append((tool, result['reason']))
        expected_codes = {service_codes(task_id)[name] for name in reference['failed_services']}
        passed = (not rejects and reference == stored and set(reference['failed_services']) == initially_down
                  and len(viable) > 1 and viable[0][1] == reference['fix_id']
                  and bool(harmful - initially_down)
                  and env.final is not None and set(env.final['failed_services']) == expected_codes
                  and env.final['root_cause_id'] == reference['root_cause']
                  and env.underlying.committed == expected_public_fix
                  and env.committed_effect is not None and not env.committed_effect['unavailable_after']
                  and not env.committed_effect['newly_unavailable'])
        rows.append({'task_id': task_id, 'benchmark_version': VERSIONS[task_id],
                     'source_title': case['title'], 'services':len(case['facts']['topology']),
                     'unavailable_services':len(initially_down),
                     'reference_file':str(reference_path(task_id).relative_to(ROOT)),
                     'expected_repair':reference['fix_id'],
                     'scripted_tool_calls':len(trajectory), 'references_and_sandbox_pass':passed,
                     'is_provider_trial':False, 'warnings':rejects})
    return {'generated_utc':datetime.now(timezone.utc).isoformat(),
            'scope':'Only V6 counterfactual synthetic tasks. Scripted oracle traces are NOT provider evidence.',
            'tasks':rows, 'all_offline_checks_pass':all(r['references_and_sandbox_pass'] for r in rows)}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path, default=ROOT/'reports/offline_audit.json')
    args=p.parse_args()
    report=run_audit()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'tasks':len(report['tasks']), 'all_offline_checks_pass':report['all_offline_checks_pass']},indent=2))
    if not report['all_offline_checks_pass']:
        raise SystemExit(1)
if __name__=='__main__':main()
