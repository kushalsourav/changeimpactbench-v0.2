#!/usr/bin/env python3
"""Check source provenance and complete offline documentary reference replay."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from realbench.core import available,case_for,source_hashes,digest,EvidenceEnvironment,replay,ENGINE,prompt_for
from hashlib import sha256
for incident in available():
 case=case_for(incident);env=EvidenceEnvironment(case)
 calls=[('read_alert',{}),('list_evidence',{})]
 calls.extend(('read_evidence',{'evidence_id':e['id']}) for e in case['evidence'])
 calls.append(('submit_investigation',{'impact_ids':case['affected'],
     'root_cause_id':case['correct_cause'],'response_id':case['correct_response'],
     'evidence_ids':[e['id'] for e in case['evidence'][:3]],
     'rationale':'The retrieved official source evidence supports the documented incident cause and response.'}))
 turns=[];trajectory=[]
 for i,(tool,args) in enumerate(calls,1):
  obs=env.execute(tool,args)
  turns.append({'turn':i,'tool_calls':[{'id':f'call-{i}','name':tool,'args':args}]})
  trajectory.append({'turn':i,'id':f'call-{i}','observation':obs})
 record={'task_id':incident,'benchmark_version':case['benchmark_version'],
    'source_sha256':digest(case),'prompt_sha256':sha256(prompt_for(case).encode()).hexdigest(),
    'agent_framework':ENGINE,'source_hashes':source_hashes(),
    'turns':turns,'provider_requests':len(turns),'trajectory':trajectory,'tool_errors':[],
    'final_investigation':env.final,'status':'completed'}
 checked=replay(record)
 assert checked['verified'] and checked['grade']['pass'],(incident,checked)
 print(f'OK {incident} · first-party source URL · hash + deterministic reference replay')
print(f'PASS {len(available())} original published incidents, zero provider simulations')
