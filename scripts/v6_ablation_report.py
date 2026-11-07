#!/usr/bin/env python3
"""Audit real-recorded three-condition trials. Never synthesize model outputs.

Usage:
 python scripts/v6_ablation_report.py results/ui_*.jsonl --out reports/ablation.json

V4/V6 task conditions are intentionally not identical; gaps are descriptive
and are NOT an identified causal effect of prompt leakage alone.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import json
from pathlib import Path
from math import sqrt
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from dashboard_data import audit_record

def ci_wilson(pass_count: int, n: int) -> list[float] | None:
    if not n:return None
    z=1.96;p=pass_count/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den
    half=z*sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [round(max(0,center-half),4),round(min(1,center+half),4)]

def condition(task_id: str) -> str | None:
    return ('v4' if task_id.endswith('V4') else
            'v6_neutral' if task_id.endswith('V6N') else
            'v6_counterfactual' if task_id.endswith('V6CF') else None)

def build_report(files: list[str]) -> dict:
    groups=defaultdict(list); seen=set(); included=[]
    for name in files:
        path=Path(name)
        for line_no,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
            if not line.strip():continue
            rec=json.loads(line)
            cond=condition(rec.get('task_id',''))
            if not cond:continue
            key=(rec.get('task_id'),rec.get('model_requested'),rec.get('trial'),rec.get('timestamp_utc'))
            if key in seen:raise ValueError(f'Duplicate episode in trial input: {key}')
            seen.add(key)
            audit=audit_record(rec)
            version=rec.get('task_id','').split('V')[0]
            config=(rec.get('temperature_requested'),rec.get('max_tokens_requested'),rec.get('reasoning_effort_requested'))
            row={'file':str(path),'line':line_no,'task':rec.get('task_id'),'condition':cond,
                 'model':rec.get('model_requested'),'provider_model':rec.get('model_returned'),
                 'trial':rec.get('trial'),'run_timestamp':rec.get('timestamp_utc'),
                 'settings':config,'status':rec.get('status'),'audit_status':audit['status'],
                 'verified':audit['status']=='completed' and audit['reference_matches'] is True
                            and audit['prompt_sha_matches'] is True and audit['stored_grade_matches'] is True,
                 'strict_pass':(audit['grade'] or {}).get('strict_pass'),
                 'warnings':audit['warnings']}
            groups[(rec.get('model_requested'),version,cond,config)].append(row)
            included.append(row)
    cells=[]
    for (model,seed,cond,config),rows in sorted(groups.items(),key=lambda it:str(it[0])):
        valid=[r for r in rows if r['verified']]
        p=sum(r['strict_pass'] is True for r in valid)
        cells.append({'model':model,'seed':seed,'condition':cond,'settings':config,
                      'submitted':len(rows),'verified_completed':len(valid),
                      'unverified_or_transport':len(rows)-len(valid),
                      'pass_count':p, 'strict_pass_rate':round(p/len(valid),4) if valid else None,
                      'confidence_95_wilson':ci_wilson(p,len(valid)),
                      'meets_min_3_trials':len(rows)>=3 and len({r['trial'] for r in rows})>=3,
                      'has_multiple_run_dates':len({r['run_timestamp'] for r in rows})>1})
    comparisons=[]
    grouped=defaultdict(dict)
    for cell in cells:
        grouped[(cell['model'],cell['seed'],tuple(cell['settings']))][cell['condition']]=cell
    for (model,seed,config),by_condition in sorted(grouped.items(),key=lambda x:str(x[0])):
        if all(x in by_condition for x in ('v4','v6_neutral','v6_counterfactual')):
            a,b,c=(by_condition[x] for x in ('v4','v6_neutral','v6_counterfactual'))
            valid=all(x['meets_min_3_trials'] and x['unverified_or_transport']==0 for x in (a,b,c))
            comparisons.append({
                'model':model,'seed':seed,'settings':config,
                'valid_three_trial_cells':valid,
                'v4_minus_v6_neutral':round(a['strict_pass_rate']-b['strict_pass_rate'],4) if valid else None,
                'v6_neutral_minus_v6_counterfactual':round(b['strict_pass_rate']-c['strict_pass_rate'],4) if valid else None,
                'interpretation':'Descriptive condition difference, not a causal estimate of answer leakage.'
            })
    return {'method':'independent-record-replay; V4 and V6 conditions differ in task structure',
            'limitations':'Pass-rate differences are descriptive and cannot isolate title leakage from graph/tool/difficulty changes. Provider-error and unverified records remain reported.',
            'minimum_required_trials_per_model_seed_condition':3,
            'ready_to_claim_ablation':bool(cells) and all(c['meets_min_3_trials'] and c['unverified_or_transport']==0 for c in cells)
              and len({c['model'].split('/')[0] for c in cells}) >= 2
              and all({c['condition'] for c in cells if c['model']==model and c['seed']==seed} == {'v4','v6_neutral','v6_counterfactual'}
                      for model,seed in {(c['model'],c['seed']) for c in cells}),
            'cells':cells,'comparisons':comparisons,'all_trials':included}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('inputs',nargs='+',help='Real output JSONL files (no synthetic records)')
    ap.add_argument('--out',default='reports/v6_ablation_report.json')
    args=ap.parse_args();result=build_report(args.inputs)
    output=Path(args.out);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(f'{len(result["all_trials"])} real recorded trials, {len(result["cells"])} cells; complete protocol: {result["ready_to_claim_ablation"]}; {output}')
if __name__=='__main__':main()
