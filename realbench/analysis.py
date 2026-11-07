"""Optional external LLM research analyst, separate from deterministic scoring.

LLM chooses claims and chart dimensions. Python independently supplies chart values
from observed episodes: the model cannot invent rates or overwrite official grades.
"""
from __future__ import annotations
from hashlib import sha256
import json,os,re
from typing import Any
import requests
from realbench.core import case_for,digest

MODEL_ID=re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.:-]+:free$')
ALLOWED_METRICS={
    'strict_pass_pct':'Strict pass rate (%)',
    'impact_f1_pct':'Mean affected-scope F1 (%)',
    'root_accuracy_pct':'Correct root-cause selection (%)',
    'response_accuracy_pct':'Correct documented response (%)',
    'mean_score_pct':'Mean deterministic score (%)',
    'mean_tool_calls':'Mean observed tool calls',
    'mean_provider_calls':'Mean provider requests',
}


def record_hash(record):
    return sha256(json.dumps(record,ensure_ascii=False,sort_keys=True,default=str).encode()).hexdigest()


def metrics_for(records:list[dict]):
    scored=[r for r in records if r.get('status')=='completed' and isinstance(r.get('grade'),dict)]
    labels=sorted(set(r['model_requested'] for r in scored))
    rows=[]
    for model in labels:
        group=[r for r in scored if r['model_requested']==model]
        n=len(group)
        avg=lambda fn:round(sum(fn(r) for r in group)/n,2)
        rows.append({'model':model,'n':n,
            'strict_pass_pct':avg(lambda r:100*int(bool(r['grade']['pass']))),
            'impact_f1_pct':avg(lambda r:100*r['grade']['affected_f1']),
            'root_accuracy_pct':avg(lambda r:100*int(bool(r['grade']['root_correct']))),
            'response_accuracy_pct':avg(lambda r:100*int(bool(r['grade']['fix_correct']))),
            'mean_score_pct':avg(lambda r:100*r['grade']['score']),
            'mean_tool_calls':avg(lambda r:r['grade']['tool_calls']),
            'mean_provider_calls':avg(lambda r:r['provider_requests'])})
    return {'model_rows':rows,'completed_count':len(scored),'all_attempts':len(records),
            'non_gradeable_count':len(records)-len(scored),
            'metric_labels':ALLOWED_METRICS}


def evidence_refs(record):
    refs=set()
    for item in record.get('trajectory',[]):
        obs=item.get('observation',{})
        ref=obs.get('event_id')
        if ref:refs.add(ref)
        if obs.get('tool')=='read_evidence':
            eid=(obs.get('result') or {}).get('id')
            if eid:refs.add(eid)
    return refs


def validate_analysis(d:dict,record:dict,other:list[dict]):
    """Strict grounding of citations and chart plan; invalid generated text rejected."""
    if not isinstance(d,dict):raise ValueError('LLM response must be a JSON object')
    title=d.get('headline','')
    if not isinstance(title,str) or not 8<=len(title)<=180:raise ValueError('Invalid headline')
    refs=evidence_refs(record)
    findings=[]
    for x in d.get('findings',[])[:5]:
        if not isinstance(x,dict):raise ValueError('Malformed finding')
        claim=x.get('claim','');cit=x.get('evidence_ids',[])
        if not isinstance(claim,str) or not 8<=len(claim)<=500 or not isinstance(cit,list) or not set(cit)<=refs:
            raise ValueError('LLM finding cites unobserved evidence')
        findings.append({'claim':claim,'evidence_ids':cit})
    limitations=d.get('limitations',[])
    if not isinstance(limitations,list) or any(not isinstance(x,str) or len(x)>360 for x in limitations):
        raise ValueError('Invalid limitations')
    dataset=metrics_for(other)
    plans=[]
    for chart in d.get('chart_plans',[])[:3]:
        if not isinstance(chart,dict):continue
        metric=chart.get('metric_id')
        if metric not in ALLOWED_METRICS or chart.get('type') not in ('bar','scatter'):
            continue
        # Fully DERIVED by code, never accepted as model-supplied values.
        if dataset['completed_count']<1:continue
        plans.append({'type':chart['type'],'metric_id':metric,
             'metric_label':ALLOWED_METRICS[metric],
             'title':str(chart.get('title','Observed episodes'))[:110],
             'reason':str(chart.get('reason',''))[:300],
             'source':'independent deterministic grade/record',
             'points':[{'model':r['model'],'value':r[metric],'n':r['n']} for r in dataset['model_rows']]})
    return {'headline':title,'findings':findings,'limitations':limitations[:5],
            'charts':plans,'grounded_event_ids':sorted(refs),
            'method':'LLM-authored narrative and chart choice; numeric chart values independently computed'}


def request_analysis(record,related,model,token):
    if not MODEL_ID.fullmatch(model):raise ValueError('Choose a free-model ID for analyst')
    if not token:raise ValueError('OPENROUTER_API_KEY missing')
    case=case_for(record['task_id'])
    grade=record.get('grade')
    if not isinstance(grade,dict):
        raise ValueError('Only completed independently graded episodes can be summarized')
    allowed=evidence_refs(record)
    observed=[]
    for x in record.get('trajectory',[]):
        obs=x['observation']
        result=obs.get('result',{})
        # No hallucinated model thoughts; tool observations only.
        observed.append({'event_id':obs['event_id'],'tool':obs['tool'],
                         'result':result if obs['tool']=='read_evidence' else str(result)[:650]})
    authoritative=metrics_for(related)
    prompt={
       'task': 'Independently synthesize observed episode evidence. Generate original research findings, not canned templates. Choose insightful comparative chart metrics from allowed names. Do not manufacture observations, numeric values, citations or hidden thoughts.',
       'source':{'organisation':case['organisation'],'title':case['source_title'],
                 'url':case['source_url'],'origin':case['dataset_origin']},
       'episode':{'model':record['model_requested'],'trial':record['trial'],
                  'status':record['status'],'grade':grade,'final':record['final_investigation'],
                  'observed_tools':observed[:70]},
       'comparison_observed':authoritative,
       'allowed_evidence_ids':sorted(allowed),
       'output_schema':{'headline':'8-180 characters','findings':[{'claim':'grounded statement',
                  'evidence_ids':['EV001']}], 'limitations':['not a live production recovery'],
                  'chart_plans':[{'type':'bar','metric_id':'strict_pass_pct',
                                  'title':'chosen descriptive title','reason':'why this chart helps'}]},
       'chart_rule':'Select 0-3 useful charts by TYPE and METRIC ID only; DO NOT produce point values; backend derives values.',
       'accuracy_note':'Grade checks structured I/H/R selections and evidence provenance, not the semantic correctness of the free-text rationale. Cite real observed evidence IDs; source postmortem is not original telemetry. Avoid generalizing n=1.'}
    response=requests.post('https://openrouter.ai/api/v1/chat/completions',timeout=95,
        headers={'Authorization':f'Bearer {token}','Content-Type':'application/json',
                 'HTTP-Referer':'https://localhost','X-Title':'ChangeImpactBench source-grounded analyst'},
        json={'model':model,'messages':[{'role':'system','content':
          'You are an independent evidence analyst. Return ONLY a valid JSON object matching the requested schema. Be precise, note ambiguity, and use only provided evidence IDs. Never invent citations, numeric graph values or private model thoughts.'},
          {'role':'user','content':json.dumps(prompt,ensure_ascii=False)}],
          'temperature':0.2,'max_tokens':2800})
    response.raise_for_status()
    payload=response.json()
    content=payload['choices'][0]['message']['content']
    if not isinstance(content,str):raise ValueError('No analyst text returned')
    raw=content.strip()
    if raw.startswith('```'):
        raw=re.sub(r'^```(?:json)?\s*|\s*```$', '',raw).strip()
    proposal=json.loads(raw)
    accepted=validate_analysis(proposal,record,related)
    return {'analyst_model':model,'episode_sha256':record_hash(record),
            'comparison_hash':digest([record_hash(r) for r in related]),
            'report':accepted,'raw_analyst_output':content,
            'provider_usage':payload.get('usage',{}),'human_semantic_review':'pending',
            'independent_grade_unchanged':True}
