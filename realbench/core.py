"""Frozen, source-linked postmortem tasks and independent deterministic evidence replay.

Source material is CURATED PARAPHRASE of published first-party incident reports.
No synthetic service health, private logs, simulated repair or operational claims.
"""
from __future__ import annotations
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
INCIDENTS = HERE / 'incidents'
MAX_MODEL_CALLS = 48
MAX_TOOL_CALLS = 64
TOOLS = ('read_alert', 'list_evidence', 'read_evidence', 'inspect_timeline',
         'inspect_impact', 'list_responses', 'submit_investigation')
ENGINE = 'langchain-create-agent/real-source-postmortem-v1'


def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def digest(obj):
    return sha256(canonical(obj).encode()).hexdigest()


def available():
    return sorted(x.stem for x in INCIDENTS.glob('*.json'))


def case_for(incident_id: str) -> dict:
    if incident_id not in available():
        raise ValueError('Unknown published incident')
    case = json.loads((INCIDENTS / (incident_id + '.json')).read_text(encoding='utf-8'))
    if case['id'] != incident_id or not case['source_url'].startswith('https://'):
        raise ValueError('Invalid source-backed incident manifest')
    return case


def public_case(case: dict) -> dict:
    """No grader answers, no reference labels in the agent-visible catalog."""
    return {k: deepcopy(case[k]) for k in ('id', 'title', 'organisation', 'date',
            'source_title', 'source_url', 'source_published', 'alert',
            'dataset_origin', 'benchmark_version', 'impact_options',
            'root_hypotheses', 'response_options')}


def case_summary(case: dict) -> dict:
    result = public_case(case)
    result['evidence_count'] = len(case['evidence'])
    result['causal_graph'] = deepcopy(case['causal_graph'])
    # Reference-only data is intentionally excluded from this public catalog.
    return result


def prompt_for(case: dict) -> str:
    return ("You are investigating an actual publicly documented production incident, "
            "using only curated, paraphrased excerpts from its official public postmortem. "
            "These are NOT live monitoring tools or original production logs; you cannot modify production. "
            "Start with read_alert and investigate the evidence. Identify every affected impact category "
            "using its I-code; choose ONE root-cause H-code and ONE documented response R-code. "
            "Use structured IDs in submit_investigation, not prose in ID fields. "
            "Cite at least two E-code evidence documents you actually read, and give your own free-text rationale. "
            "Do not claim an action was executed. The final answer must use submit_investigation. "
            "The evidence may include unknowns or uncertainty; do not turn speculation into fact. "
            "Invoke at most ONE tool per model message so each source observation is ordered. Use the investigation budget efficiently. Your outputs will be independently replayed.")


class EvidenceEnvironment:
    def __init__(self, case: dict):
        self.case = deepcopy(case)
        self.steps: list[dict] = []
        self.read_ids: set[str] = set()
        self.final: dict | None = None
        self.closed = False
        self.violations: list[str] = []

    def execute(self, tool: str, args: dict) -> dict:
        if self.closed or len(self.steps) >= MAX_TOOL_CALLS:
            raise ValueError('Episode closed or tool-call limit exceeded')
        if tool not in TOOLS or not isinstance(args, dict):
            raise ValueError('Unknown native tool')
        expected = ({'evidence_id'} if tool == 'read_evidence' else
                    {'impact_ids', 'root_cause_id', 'response_id', 'evidence_ids', 'rationale'}
                    if tool == 'submit_investigation' else set())
        if set(args) != expected:
            raise ValueError(f'{tool} requires fields {sorted(expected)}')
        case = self.case
        if tool == 'read_alert':
            result = dict(public_case(case), instruction='Evaluate documented scope, cause and response; do not assert real remediation was performed.')
        elif tool == 'list_evidence':
            result = {'documents': [{'id': x['id'], 'time': x['time'], 'kind': x['kind']}
                                    for x in case['evidence']], 'full_text_withheld_until_read': True}
        elif tool == 'read_evidence':
            entry = next((x for x in case['evidence'] if x['id'] == args['evidence_id']), None)
            if entry is None:
                raise ValueError('Unknown source excerpt')
            result = deepcopy(entry)
            result['document_type'] = 'Paraphrase of published postmortem, not an original production log'
            self.read_ids.add(entry['id'])
        elif tool == 'inspect_timeline':
            result = {'timeline_index': [{'evidence_id': x['id'], 'time': x['time'], 'kind': x['kind']}
                                         for x in case['evidence']]}
        elif tool == 'inspect_impact':
            result = {'impact_categories': deepcopy(case['impact_options']),
                      'note': 'Some listed categories are unaffected distractors; verify using source evidence.'}
        elif tool == 'list_responses':
            result = {'response_options': deepcopy(case['response_options']),
                      'note': 'Select documented response, not a real executable repair.'}
        else:
            impact_ids, evidence_ids = args['impact_ids'], args['evidence_ids']
            ids = lambda key: {x['id'] for x in case[key]}
            if (not isinstance(impact_ids, list) or any(not isinstance(x, str) for x in impact_ids)
                or len(impact_ids) != len(set(impact_ids))
                or not set(impact_ids) <= ids('impact_options')
                or args['root_cause_id'] not in ids('root_hypotheses')
                or args['response_id'] not in ids('response_options')
                or not isinstance(evidence_ids, list)
                or any(not isinstance(x, str) for x in evidence_ids)
                or len(evidence_ids) != len(set(evidence_ids))
                or not set(evidence_ids) <= {x['id'] for x in case['evidence']}
                or not isinstance(args['rationale'], str) or len(args['rationale'].strip()) < 15):
                raise ValueError('Malformed final submission; provide valid I/H/R/E IDs and rationale')
            self.final = deepcopy(args)
            self.closed = True
            result = {'accepted': True, 'final_submission_recorded': True,
                      'operation': 'documentary evaluation only; no production action performed'}
        event_id = f'EV{len(self.steps)+1:03d}'
        observation = {'event_id': event_id, 'tool': tool, 'result': result}
        self.steps.append({'tool': tool, 'arguments': deepcopy(args), 'observation': observation})
        return observation


def f1_score(expected, predicted):
    a,b=set(expected),set(predicted)
    return 1.0 if not a and not b else 0.0 if not a or not b else 2*len(a&b)/(len(a)+len(b))


def source_hashes() -> dict:
    return {path.name:sha256(path.read_bytes()).hexdigest()
            for path in (HERE/'core.py', HERE/'runner.py', HERE/'analysis.py')}


def replay(record: dict) -> dict:
    """Do not trust stored observations, model self-grade, or LLM commentary."""
    try:
        c=case_for(record['task_id'])
    except (KeyError, ValueError):
        return {'verified':False,'warnings':['Unknown source incident'],'grade':None}
    failures=[]
    if record.get('benchmark_version') != c['benchmark_version'] or record.get('source_sha256') != digest(c):
        failures.append('Frozen public source manifest hash mismatch')
    if record.get('prompt_sha256') != sha256(prompt_for(c).encode()).hexdigest():
        failures.append('Frozen prompt hash mismatch')
    if record.get('agent_framework') != ENGINE or record.get('source_hashes') != source_hashes():
        failures.append('Engine/source implementation hash mismatch')
    turns=record.get('turns',[])
    if (not isinstance(turns,list) or len(turns)>MAX_MODEL_CALLS
        or record.get('provider_requests') != len(turns)):
        failures.append('Provider turn count discrepancy')
        turns=[]
    env=EvidenceEnvironment(c)
    replay_events=[]
    replay_errors=[]
    for i,turn in enumerate(turns,1):
        if turn.get('turn') != i or not isinstance(turn.get('tool_calls'),list):
            failures.append('Non-sequential provider turns')
            break
        for call in turn['tool_calls']:
            try:
                obs=env.execute(call['name'],call['args'])
                replay_events.append({'turn':i,'id':call.get('id'),'observation':obs})
            except (ValueError, KeyError, TypeError) as exc:
                replay_errors.append({'turn':i,'reason':str(exc)})
    if record.get('trajectory') != replay_events:
        failures.append('Native tool results do not match independent replay')
    if record.get('tool_errors',[]) != replay_errors:
        failures.append('Rejected tool attempts mismatch')
    if record.get('final_investigation') != env.final:
        failures.append('Final investigation differs from native replay')
    if failures:
        return {'verified':False,'warnings':failures,'grade':None}
    if record.get('status') != 'completed':
        return {'verified':True,'warnings':[], 'grade':None}
    if env.final is None:
        return {'verified':False,'warnings':['Completed record lacks terminal submission'], 'grade':None}
    final=env.final
    impact=f1_score(c['affected'],final['impact_ids'])
    cause=final['root_cause_id']==c['correct_cause']
    response=final['response_id']==c['correct_response']
    citations=set(final['evidence_ids'])
    evidence_ok=len(citations)>=2 and citations<=env.read_ids
    disciplined=not replay_errors
    strict=(set(final['impact_ids'])==set(c['affected']) and cause and response and evidence_ok and disciplined)
    score=round(.20*impact+.25*int(cause)+.30*int(response)+.15*int(evidence_ok)+.10*int(disciplined),5)
    grade={'pass':strict,'strict_pass':strict,'score':score,'affected_f1':round(impact,5),
           'root_correct':cause,'fix_correct':response,'evidence_score':10 if evidence_ok else 0,
           'procedure_score':10 if disciplined else 0,'recovery_success':None,
           'recovery_safe':None,'unsafe_commit':None,
           'evidence_review':'Source citation IDs were read before submission; semantic interpretation requires human review',
           'impact_expected':list(c['affected']),'impact_predicted':list(final['impact_ids']),
           'correct_cause_id':c['correct_cause'],'predicted_cause_id':final['root_cause_id'],
           'correct_response_id':c['correct_response'],'predicted_response_id':final['response_id'],
           'protocol_errors':replay_errors,'documentary_only':True,
           'tool_calls':len(replay_events),'source_url':c['source_url']}
    return {'verified':True,'warnings':[], 'grade':grade}
