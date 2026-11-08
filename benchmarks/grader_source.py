"""Deterministic, judge-free scorer for the six source-derived incident graders (v2).

Place with RW01.json..RW06.json in benchmarks/source_graders/. Additive: it never
alters a stored grade and sits outside implementation_hashes().

Pipeline: split the report into clauses -> match each ground-truth claim with
polarity and contradiction checks -> detect hallucination traps -> weight ->
auditable result. No model or human decision enters the scoring path.

Limits: matching is lexical. Negation is detected within a six-word window and
clause splits, so heavy paraphrase can be missed. The result is reproducible,
not a proof of semantic understanding.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "source_graders"
CONTRACT = 'source-grader-2'
DIMENSIONS = ('observed_symptoms', 'confirmed_root_cause', 'investigation_evidence',
              'recovery_actions', 'recovery_verification', 'acceptable_alternatives')
WEIGHTS = {'observed_symptoms': 15, 'confirmed_root_cause': 25, 'investigation_evidence': 15,
           'recovery_actions': 20, 'recovery_verification': 15, 'acceptable_alternatives': 10}
TRAP_PENALTY = 3
CRITICAL_MULTIPLIER = 2

_CLAUSE_SPLIT = re.compile(r'\.(?=\s|$)|[;!?\n]+|\b(?:although|but|while|whereas|however)\b')
_NEG = re.compile(r"\b(?:not|no|never|without|neither|nor|none|cannot|ruled out|dismissed|excluded|"
                  r"rejected|avoid\w*|prevent\w*)\b|n't\b")
_REJECT = re.compile(r"\b(?:unsafe|not safe|reject\w*|avoid\w*|risk\w*|could not|unable|cannot|impossible|"
                     r"not feasible|not possible|ruled out|diverg\w*|contradict\w*|not supported|not viable)\b")
_PERFORMED = re.compile(r"\b(?:performed|executed|completed|carried out|was deployed|were deployed|"
                        r"implemented|engineers applied|engineers made)\b")


def seed_of(task_id: str) -> str:
    # Source postmortems describe only the historical V4 tasks. Never silently
    # apply historical facts to a counterfactual, neutral, or other synthetic case.
    match = re.fullmatch(r'(RW0[1-6])(?:V4)?', task_id)
    if not match:
        raise ValueError(f'Unrecognized task id: {task_id}')
    return match.group(1)


def load_source(task_id: str) -> dict:
    return json.loads((ROOT / f'{seed_of(task_id)}.json').read_text(encoding='utf-8'))


def _norm(text) -> str:
    if isinstance(text, (list, tuple)):
        text = ' '.join(str(t) for t in text)
    return str(text or '').lower().replace('\u2019', "'").replace('\u2013', '-').replace('\u2014', '-')


def clauses(text) -> list[str]:
    return [c.strip() for c in _CLAUSE_SPLIT.split(_norm(text)) if c.strip()]


def _pat(term: str) -> re.Pattern:
    return re.compile(r'\b' + re.escape(term.lower()))


def _hits(clause: str, terms) -> list[re.Match]:
    return [m for t in terms for m in _pat(t).finditer(clause)]


def negated_at(clause: str, pos: int) -> bool:
    window = ' '.join(clause[:pos].split()[-6:])
    return bool(_NEG.search(window))


def asserts(clause: str, subject, predicate, polarity: str = 'pos', neg_phrases=()) -> bool:
    if not _hits(clause, subject):
        return False
    matches = _hits(clause, predicate)
    if polarity == 'pos':
        return any(not negated_at(clause, m.start()) for m in matches)
    return any(negated_at(clause, m.start()) for m in matches) or bool(_hits(clause, neg_phrases))


def eval_claim(claim: dict, cls: list[str]) -> dict:
    pol = claim.get('polarity', 'pos')
    matched = any(asserts(c, claim['subject'], claim['predicate'], pol, claim.get('neg_phrases', ())) for c in cls)
    for spec in claim.get('contradict', []):
        if any(asserts(c, spec['subject'], spec['predicate'], 'pos') for c in cls):
            return {'passed': False, 'reason': 'contradicted_by_asserted_opposite'}
    return {'passed': matched, 'reason': 'matched' if matched else 'no_clause_matches_claim'}


def eval_alternatives(catalog: list[dict], cls: list[str]) -> dict:
    items, proposed, correct = [], 0, 0
    for entry in catalog:
        hit = [c for c in cls if _hits(c, entry['terms'])]
        if not hit:
            continue
        proposed += 1
        ok, reason = True, 'consistent_with_source'
        if entry['status'] == 'source_contradicted':
            if not any(_REJECT.search(c) or _NEG.search(c) for c in hit):
                ok, reason = False, 'contradicted_option_not_rejected'
        elif not entry['performed_ok']:
            for c in hit:
                m = _PERFORMED.search(c)
                if m and not negated_at(c, m.start()):
                    ok, reason = False, 'non_performed_option_presented_as_performed'
                    break
        correct += ok
        items.append({'id': entry['id'], 'status': entry['status'], 'passed': ok, 'reason': reason})
    return {'proposed': proposed, 'correct': correct, 'items': items}


def score_report(task_id: str, report: dict | None = None, flat_text: str | None = None) -> dict:
    """report maps dimension -> text or list of text; flat_text applies one text to every dimension."""
    src = load_source(task_id)
    rules = src['scoring_rules']
    texts = {d: (_norm(flat_text) if flat_text is not None else _norm((report or {}).get(d, ''))) for d in DIMENSIONS}
    full = ' '.join(texts.values()) if flat_text is None else _norm(flat_text)
    dim_clauses = {d: clauses(t) for d, t in texts.items()}

    dims = {}
    for d in DIMENSIONS[:-1]:
        items, total, earned = [], 0, 0
        for claim in (c for c in rules['claims'] if c['dimension'] == d):
            w = CRITICAL_MULTIPLIER if claim['critical'] else 1
            res = eval_claim(claim, dim_clauses[d])
            total += w
            earned += w if res['passed'] else 0
            items.append({'id': claim['id'], 'critical': claim['critical'], 'weight': w,
                          'passed': res['passed'], 'reason': res['reason'], 'ref': claim['ref']})
        dims[d] = {'weight': WEIGHTS[d], 'earned_points': earned, 'total_points': total,
                   'score': round(WEIGHTS[d] * earned / total, 4) if total else 0.0, 'items': items}

    alt = eval_alternatives(rules['alternatives_catalog'], dim_clauses['acceptable_alternatives'])
    applicable = alt['proposed'] > 0
    dims['acceptable_alternatives'] = {
        'weight': WEIGHTS['acceptable_alternatives'], 'applicable': applicable,
        'proposed': alt['proposed'], 'correct': alt['correct'], 'items': alt['items'],
        'score': round(WEIGHTS['acceptable_alternatives'] * alt['correct'] / alt['proposed'], 4) if applicable else None,
    }

    included = [d for d in DIMENSIONS if d != 'acceptable_alternatives' or applicable]
    scale = 100 / sum(WEIGHTS[d] for d in included)
    raw = round(sum(dims[d]['score'] for d in included) * scale, 4)

    all_clauses = clauses(full)
    triggered = [{'id': t['id'], 'text': t['text']} for t in rules['traps']
                 if any(asserts(c, t['subject'], t['predicate'], 'pos') for c in all_clauses)]
    final = round(max(0.0, raw - TRAP_PENALTY * len(triggered)), 4)

    return {
        'contract': CONTRACT, 'grader_id': src['grader_id'], 'source_url': src['source']['url'],
        'dimensions': dims, 'raw_score': raw, 'traps_triggered': triggered,
        'trap_penalty': TRAP_PENALTY * len(triggered), 'final_score': final,
        'alternatives_dimension': 'scored' if applicable else 'not_applicable_renormalized',
        'source_discrepancies': src['source_discrepancies'],
        'deterministic': True, 'uses_judge': False, 'semantic_validation': 'not_performed',
        'note': 'Lexical polarity-aware matching; reproducible but not a semantic proof.',
    }


# ----- repo integration ---------------------------------------------------

def report_from_final(final: dict) -> dict:
    """Map a submit_diagnosis payload onto the sections it can actually evidence."""
    why, how = final.get('root_cause_explanation', ''), final.get('rationale', '')
    return {'confirmed_root_cause': why, 'recovery_actions': how, 'acceptable_alternatives': how}


def action_source_status(task_id: str, action_id: str) -> str:
    return load_source(task_id)['fixture_alignment']['actions'].get(action_id, {}).get('source_status', 'unverified')


def audit_record(record: dict) -> dict:
    """Replay the frozen record, then apply the source scorer to its final diagnosis."""
    # Reject before replaying: V6CF is counterfactual and must be graded with
    # its synthetic oracle, not against the historical RWxx postmortem.
    seed_of(record['task_id'])
    from benchmarks.grader import replay_record  # lazy repo import
    replay = replay_record(record)
    if not replay['verified'] or replay['grade'] is None:
        return {'contract': CONTRACT, 'verified': False, 'warnings': replay.get('warnings', [])}
    committed = replay['grade']['committed_action']
    return {'verified': True, 'historical_grade': replay['grade'],
            'committed_action_source_status': action_source_status(record['task_id'], committed),
            'source_score': score_report(record['task_id'], report_from_final(replay['predicted'])),
            'source_grade_is_supplementary': True,
            'source_semantics_verified': False,
            'source_scoring_note': 'Lexical source score is not an independent historical ground-truth adjudication.'}
