"""Post-run Research Lab analysis, backed by independently regraded native traces.

The Python verifier owns every numerical grade, repair comparison, strict verdict,
chart value, and run identity. Gemini only authors a separately labeled narrative.
This module never modifies the runner, benchmark fixtures, grader, or raw JSONL.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import re
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.services.storage import RESULTS, records_for, run_manifest
from dashboard_data import audit_record
from benchmarks.spec import get_spec, source_case
from oracle import reference_answer

router = APIRouter()


class SynthesisRequest(BaseModel):
    model: str
    confirm: bool = False


class ResearchSynthesis(BaseModel):
    headline: str = Field(min_length=12, max_length=180)
    interpretation: str = Field(min_length=30, max_length=1500)
    observations: list[str] = Field(min_length=1, max_length=5)
    limitations: str = Field(min_length=20, max_length=900)
    chart_choice: Literal['score_by_model', 'outcome_rates', 'error_counts']
    chart_explanation: str = Field(min_length=12, max_length=450)
    supporting_episodes: list[int] = Field(min_length=1, max_length=30)


def facts_for(records: list[dict]) -> dict:
    """Verifier-owned observations. No stored grade or model-written claim is trusted."""
    items = []
    for i, record in enumerate(records):
        audit = audit_record(record)
        grade = audit.get('grade') or {}
        task_id = record.get('task_id')
        case = source_case(task_id)
        reference = reference_answer(case)
        costs = {action['id']: action['cost'] for action in case['actions']}
        committed = grade.get('committed_action')
        optimal = reference['fix_id']
        gradeable = (audit.get('status') == 'completed'
                     and audit.get('prompt_sha_matches') is True
                     and audit.get('reference_matches') is True
                     and audit.get('stored_grade_matches') is True
                     and bool(grade) and grade.get('source_provisional') is not True)
        committed_cost = costs.get(committed)
        optimal_cost = costs[optimal]
        multi_tool_turns = [turn.get('turn') for turn in record.get('turns', [])
                            if isinstance(turn, dict) and len(turn.get('tool_calls') or []) > 1]
        replay_warnings = list(record.get('audit_warnings') or [])
        replay_diagnostic = ('multiple_native_tools_in_provider_response' if
                             multi_tool_turns and any('tool attempts differ' in str(w).lower() for w in replay_warnings)
                             else 'replay_not_verified' if audit.get('status') == 'unverified'
                             else None)
        items.append({
            'episode': i, 'trial': record.get('trial'), 'task': task_id,
            'model': record.get('model_requested'),
            'status': audit.get('status'), 'error_category': record.get('error_category') or replay_diagnostic,
            'multi_tool_provider_turns': multi_tool_turns,
            'audit_warnings': replay_warnings,

            'verified': gradeable,
            'integrity': {
                'prompt': audit.get('prompt_sha_matches') is True,
                'reference': audit.get('reference_matches') is True,
                'stored_grade': audit.get('stored_grade_matches') is True,
            },
            'strict_pass': grade.get('strict_pass') if gradeable else None,
            'partial_score': grade.get('score') if gradeable else None,
            'impact_f1': grade.get('affected_f1') if gradeable else None,
            'root_correct': grade.get('root_correct') if gradeable else None,
            'recovery_success': grade.get('recovery_success') if gradeable else None,
            'recovery_safe': grade.get('recovery_safe') if gradeable else None,
            'unsafe_commit': grade.get('unsafe_commit') if gradeable else None,
            'root_cause_id_submitted': grade.get('root_cause_id_submitted') if gradeable else None,
            'root_cause_id_expected': grade.get('root_cause_id_expected') if gradeable else None,
            'criterion_scores': grade.get('criterion_scores') if gradeable else None,
            'strict_failure_reasons': grade.get('strict_failure_reasons', []) if gradeable else [],
            'semantic_explanation_review': 'human evidence review pending; free-form text not scored',
            'tool_calls': record.get('tool_calls'),
            'provider_requests': record.get('provider_requests'),
            'committed_action': committed if gradeable else None,
            'committed_cost': committed_cost if gradeable else None,
            'reference_optimal_action': optimal if gradeable else None,
            'reference_optimal_cost': optimal_cost if gradeable else None,
            'repair_cost_delta': (committed_cost - optimal_cost) if gradeable and committed_cost is not None else None,
            'protocol_errors': len(grade.get('protocol_errors') or []) if gradeable else len(record.get('protocol_errors') or []),
            'gradeable': gradeable,
        })
    return {
        'episodes': items,
        'source_postmortems': sorted({get_spec(x['task']).source_url for x in items}),
        'origin': 'documented external incidents; all simulator topology, metrics, costs and counterfactual repairs are reconstructed',
        'replay': 'deterministic Python re-evaluation of recorded native tool calls',
    }


def verifier_summary(facts: dict) -> dict:
    """Numbers and strict failure taxonomy are NEVER sourced from an LLM."""
    episodes = facts['episodes']
    gradeable = [x for x in episodes if x['gradeable']]
    return {
        'episode_count': len(episodes),
        'gradeable_count': len(gradeable),
        'strict_passes': sum(x['strict_pass'] is True for x in gradeable),
        'strict_failures': sum(x['strict_pass'] is False for x in gradeable),
        'complete_safe_recoveries': sum(x['recovery_success'] is True and x['recovery_safe'] is True for x in gradeable),
        'ungradeable_count': len(episodes) - len(gradeable),
        'ungradeable_by_reason': {reason: sum(not x['gradeable'] and (x.get('error_category') or x['status']) == reason for x in episodes)
                                   for reason in sorted({x.get('error_category') or x['status'] for x in episodes if not x['gradeable']})},

        'episodes': [dict(x) for x in episodes],
        'data_origin': 'Independent Python oracle and stored native tool replay; not Google-generated content',
    }


def chart_rows(facts: dict, kind: str) -> list[dict]:
    items = [x for x in facts['episodes'] if x['gradeable']]
    if kind == 'error_counts':
        return [{'label': label, 'value': sum(1 for x in items if condition(x)), 'denominator': len(items)}
                for label, condition in [
                    ('Impact error', lambda x: x['impact_f1'] is not None and x['impact_f1'] < 1),
                    ('Root error', lambda x: x['root_correct'] is False),
                    ('Recovery incomplete', lambda x: x['recovery_success'] is False),
                    ('Unsafe repair', lambda x: x['unsafe_commit'] is True),
                    ('Non-optimal repair', lambda x: 'repair_not_reference_optimal' in x.get('strict_failure_reasons', [])),
                    ('Protocol error', lambda x: x['protocol_errors'] > 0),
                ]]
    models = sorted({x['model'] for x in items})
    rows = []
    for model in models:
        selected = [x for x in items if x['model'] == model]
        n = len(selected)
        if kind == 'score_by_model':
            value = 100 * sum(x['partial_score'] for x in selected) / n
        else:
            value = 100 * sum(x['strict_pass'] is True for x in selected) / n
        rows.append({'label': model, 'value': round(value, 2), 'denominator': n})
    return rows


def _path(filename: str):
    return RESULTS / f'{filename[:-6]}.synthesis.json'


def _fingerprint(records: list[dict]):
    return sha256(''.join(json.dumps(r, sort_keys=True, ensure_ascii=False, default=str) + '\n'
                          for r in records).encode()).hexdigest()


def _experiment_identity(filename: str, records: list[dict]) -> tuple[str | None, str]:
    """Use a verified run manifest before any episode metadata; never invent IDs."""
    manifest = run_manifest(filename)
    if manifest and isinstance(manifest.get('experiment_id'), str) and manifest['experiment_id']:
        return manifest['experiment_id'], 'run_manifest'
    ids = {r.get('experiment_id') for r in records if isinstance(r.get('experiment_id'), str) and r.get('experiment_id')}
    if len(ids) == 1:
        return ids.pop(), 'episode_metadata'
    return None, 'unavailable'


def _narrative_checks(summary: ResearchSynthesis, facts: dict) -> list[str]:
    """Conservative guardrails; NOT a substitute for human semantic review.

    Reject summaries hiding strict failures or explicitly claiming success where
    the deterministic grader shows failure. Do not make any score decisions here.
    """
    gradeable = [x for x in facts['episodes'] if x['gradeable']]
    strict_failures = [x for x in gradeable if x['strict_pass'] is False]
    text = ' '.join([summary.headline, summary.interpretation, *summary.observations, summary.chart_explanation]).lower()
    warnings = []
    if strict_failures:
        explicitly_distinguished = (
            bool(re.search(r'\bstrict\b.{0,65}\b(fail(?:ed|ure|s)?|not pass(?:ed)?|did not pass|0%)\b', text))
            or bool(re.search(r'\b(fail(?:ed|ure|s)?|did not pass)\b.{0,65}\bstrict\b', text))
        )
        if not explicitly_distinguished:
            warnings.append('Narrative does not explicitly distinguish strict FAIL from successful recovery')
    if any('repair_not_reference_optimal' in x.get('strict_failure_reasons', []) for x in strict_failures):
        if not re.search(r'\b(non[- ]?optimal|not (?:cost[- ]?)?optimal|lowest[- ]cost|more expensive|higher[- ]cost|costlier|repair cost)\b', text):
            warnings.append('Narrative omits non-optimal repair cost as a strict failure reason')
    # Clear contradictions are blocked; broader semantic review remains human.
    if any(x['protocol_errors'] > 0 for x in gradeable) and re.search(
            r'\b(?:zero|no|none)\s+(?:recorded\s+)?protocol\s+(?:errors|violations|infractions)\b', text):
        warnings.append('Narrative claims no protocol errors, but rejected requests were recorded')
    if any(x['unsafe_commit'] is True for x in gradeable) and re.search(
            r'\b(?:no|zero|without)\s+unsafe\s+(?:commits|repairs|actions)\b', text):
        warnings.append('Narrative claims no unsafe commits, contrary to replayed outcomes')
    if gradeable and all(x['strict_pass'] is False for x in gradeable) and re.search(
            r'\bstrict\s+(?:pass|success)\s+(?:was\s+)?(?:achieved|confirmed|recorded)\b', text):
        warnings.append('Narrative incorrectly claims a strict pass for an all-failed sample')
    if not gradeable:
        warnings.append('No independently gradeable episodes')
    return warnings


def _base_response(filename: str, records: list[dict], facts: dict) -> dict:
    identity, identity_source = _experiment_identity(filename, records)
    return {
        'experiment_id': identity,
        'experiment_id_source': identity_source,
        'run_file': filename,
        'verified_facts': verifier_summary(facts),
        'record_sha256': _fingerprint(records),
    }


@router.get('/api/runs/{filename}/synthesis')
def get_synthesis(filename: str):
    records = records_for(filename)
    facts = facts_for(records)
    base = _base_response(filename, records, facts)
    path = _path(filename)
    if not path.exists():
        return {'available': False, **base}
    try:
        result = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        return {'available': False, 'error': 'Unreadable saved synthesis', **base}
    if not isinstance(result, dict):
        return {'available': False, 'error': 'Invalid saved synthesis object', **base}
    if result.get('record_sha256') != base['record_sha256']:
        return {'available': False, 'stale': True, **base}
    # Never trust cached numerical chart rows: recompute them on every read.
    # Legacy generated prose may omit or contradict strict failure details;
    # suppress it rather than silently presenting an inaccurate interpretation.
    saved_guard = result.get('narrative_validation')
    result.update(base)
    try:
        summary = ResearchSynthesis.model_validate(result.get('synthesis'))
        warnings = _narrative_checks(summary, facts)
        if not valid_supporting_episodes(summary.supporting_episodes, facts):
            warnings.append('Narrative cites an invalid or non-gradeable episode')
    except (ValueError, TypeError):
        summary, warnings = None, ['Saved AI narrative has invalid structure']
    if warnings:
        result['narrative_validation'] = {
            'status': 'blocked_inconsistent', 'warnings': warnings,
            'note': 'Original sidecar unchanged; use verifier facts or regenerate the AI summary',
        }
        result['synthesis'] = None
    elif not isinstance(saved_guard, dict) or saved_guard.get('status') != 'passed_guardrails':
        result['narrative_validation'] = {
            'status': 'legacy_unvalidated',
            'warnings': ['Earlier narrative predates v0.9.21 guardrails; human semantic review is still required.'],
        }
    if summary is not None:
        chart_kind = summary.chart_choice
        result['chart'] = {'type': chart_kind, 'rows': chart_rows(facts, chart_kind),
                           'data_origin': 'Computed from independent deterministic regrades, not generated by the LLM'}
    else:
        # A blocked Gemini narrative is not a reason to hide verified metrics.
        # Keep an error-category chart calculated exclusively from audit facts.
        result['chart'] = {'type': 'error_counts', 'rows': chart_rows(facts, 'error_counts'),
                           'data_origin': 'Computed from independent deterministic regrades, not generated by the LLM'}
    return result


def valid_supporting_episodes(indices: list[int], facts: dict) -> bool:
    """Only verified zero-based episode indices may substantiate Gemini prose."""
    episodes = facts['episodes']
    return bool(indices) and all(isinstance(i, int) and 0 <= i < len(episodes)
                                 and episodes[i]['gradeable'] for i in indices)


def research_payload(facts: dict) -> dict:
    """Minimize what Gemini sees: only gradeable evidence can be cited.

    Original indices are retained; do not renumber after filtering. Summary
    counts describe the whole sample, but invalid episodes have no outcome
    details to misquote or mistake for grades.
    """
    gradeable = [x for x in facts['episodes'] if x['gradeable']]
    excluded = [dict(episode=x['episode'], model=x['model'], task=x['task'],
                     status=x['status'], error_category=x['error_category'])
                for x in facts['episodes'] if not x['gradeable']]
    return {'gradeable_episodes': gradeable, 'non_gradeable_episodes_status_only': excluded,
            'gradeable_episode_ids': [x['episode'] for x in gradeable],
            'strict_passes': sum(x['strict_pass'] is True for x in gradeable),
            'strict_failures': sum(x['strict_pass'] is False for x in gradeable),
            'total_episodes': len(facts['episodes']), 'gradeable_count': len(gradeable),
            'origin': facts['origin'], 'replay': facts['replay']}


def verified_fallback(filename: str, records: list[dict], facts: dict, model: str,
                      warnings: list[str]) -> dict:
    """Save a useful deterministic-only sidecar when Gemini is not citable.

    Never silently rewrite Gemini episode references and never fabricate a
    textual interpretation or assign scores to unverified runs.
    """
    return {
        'available': False, 'generated_utc': datetime.now(timezone.utc).isoformat(),
        'model': model, **_base_response(filename, records, facts),
        'record_tasks': sorted({r.get('task_id') for r in records}),
        'record_models': sorted({r.get('model_requested') for r in records}),
        'label': 'Verifier-only result; AI interpretation withheld',
        'narrative_validation': {'status': 'blocked_inconsistent', 'warnings': warnings,
                                 'note': 'The verifier-owned results remain available; no Gemini narrative is cited'},
        'synthesis': None,
        'chart': {'type': 'error_counts', 'rows': chart_rows(facts, 'error_counts'),
                  'data_origin': 'Computed from independent deterministic regrades, not generated by the LLM'},
        'episode_count': len(records),
        'gradeable_count': sum(x['gradeable'] for x in facts['episodes']),
        'sources': facts['source_postmortems'],
    }


@router.post('/api/runs/{filename}/synthesis')
def generate_synthesis(filename: str, request: SynthesisRequest):
    if not request.confirm:
        raise HTTPException(400, 'Approve one additional LLM summarization request')
    from api.services.gemini_catalog import PREFIX, allowed_model_ids, google_key_ready
    if request.model not in allowed_model_ids() or not request.model.startswith(PREFIX):
        raise HTTPException(400, 'Select an approved Google AI Studio research model')
    if not google_key_ready():
        raise HTTPException(400, 'Google API key not configured on server')
    records = records_for(filename)
    if not records:
        raise HTTPException(400, 'No saved episodes')
    if len(records) > 30:
        raise HTTPException(400, 'Summarization limited to 30 episodes')
    facts = facts_for(records)
    if not any(x['gradeable'] for x in facts['episodes']):
        raise HTTPException(400, 'No independently verified, gradeable episode available')
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        model = ChatGoogleGenerativeAI(
            model=request.model.removeprefix('google-ai-studio/'),
            google_api_key=(os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')),
            max_output_tokens=2300, max_retries=0,
        )
        analyzer = model.with_structured_output(ResearchSynthesis, method='json_schema')
        output = analyzer.invoke([
            ('system', 'You are an independent SRE research analyst. Analyze ONLY the provided independently verified episode facts, never hidden reasoning. '
             'IMPORTANT: An episode may have safe complete recovery and a high weighted partial score yet strictly FAIL due to a more expensive/non-optimal repair. '
             'Explicitly state the strict PASS or FAIL outcome and its recorded reasons; for non-optimal repairs report the committed and optimal repair IDs and their modeled costs. '
             'For each strict failure do not call it an overall success. Do not claim a strict pass based on high partial score. '
             'Distinguish rejected tool requests, repair safety, incomplete recovery, and root-cause ID classification. '
             'A rejected request alone does not mean an unsafe commit; these outcome-v4 runs may still strictly pass. '
             'Free-form explanations and evidence semantics await human review; root IDs are matched exactly. '
             'The original investigation is a live model run, while replay is deterministic without inference. '
             'Topology, costs and telemetry are synthetic reconstructions, not production measurements. '
             'State small sample limitations. IMPORTANT: cite only gradeable_episode_ids as zero-based supporting_episodes. '
             'Unverified and API-error episodes may be discussed as reliability limitations by their status only, '
             'never as a grade, recovery, repair success, or supporting evidence. '
             'The verifier owns every numerical chart value; you choose only its type and write prose.'),
            ('human', json.dumps(research_payload(facts), ensure_ascii=False)),
        ])
        summary = output if isinstance(output, ResearchSynthesis) else ResearchSynthesis.model_validate(output)
    except Exception as exc:
        raise HTTPException(502, f'Google Research Lab synthesis failed: {type(exc).__name__}; deterministic results remain unchanged') from exc
    narrative_warnings = _narrative_checks(summary, facts)
    if not valid_supporting_episodes(summary.supporting_episodes, facts):
        narrative_warnings.append('Gemini cited an invalid or non-gradeable episode; interpretation withheld')
    if narrative_warnings:
        fallback = verified_fallback(filename, records, facts, request.model, narrative_warnings)
        _path(filename).write_text(json.dumps(fallback, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        return fallback
    data = summary.model_dump()
    result = {
        'available': True,
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'model': request.model,
        **_base_response(filename, records, facts),
        'record_tasks': sorted({r.get('task_id') for r in records}),
        'record_models': sorted({r.get('model_requested') for r in records}),
        'label': 'LLM interpretation; not deterministic verdict or human-verified semantics',
        'narrative_validation': {
            'status': 'passed_guardrails',
            'warnings': [],
            'note': 'Basic automated checks only; explanation semantics still require human review',
        },
        'synthesis': data,
        'chart': {
            'type': data['chart_choice'],
            'rows': chart_rows(facts, data['chart_choice']),
            'data_origin': 'Computed from independent deterministic regrades, not generated by the LLM',
        },
        'episode_count': len(records),
        'gradeable_count': sum(x['gradeable'] for x in facts['episodes']),
        'sources': facts['source_postmortems'],
    }
    _path(filename).write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result
