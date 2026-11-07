'use client';
import { useEffect, useState } from 'react';
import { BarChart, Bar, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { API } from '../lib/api';
import { Panel } from './ui';
import { modelDisplay, short } from '../lib/presentation';

type VerifiedEpisode = {
  episode: number; trial?: number; task: string; model: string; status: string;
  gradeable: boolean; strict_pass: boolean | null; partial_score: number | null;
  recovery_success: boolean | null; recovery_safe: boolean | null;
  strict_failure_reasons: string[]; protocol_errors: number;
  committed_action: string | null; committed_cost: number | null;
  reference_optimal_action: string | null; reference_optimal_cost: number | null;
  repair_cost_delta: number | null;
  error_category?:string|null; multi_tool_provider_turns?:number[]; audit_warnings?:string[];
  integrity: {prompt:boolean; reference:boolean; stored_grade:boolean};
};
type VerifiedFacts = {
  episode_count:number; gradeable_count:number; strict_passes:number; strict_failures:number;
  complete_safe_recoveries:number; episodes:VerifiedEpisode[]; data_origin:string;
};
type SynthesisResult = {
  available:boolean; stale?:boolean; experiment_id?:string|null; experiment_id_source?:string;
  run_file?:string; model?:string; label?:string; episode_count?:number;
  gradeable_count?:number; verified_facts?:VerifiedFacts;
  narrative_validation?:{status:string;warnings:string[];note?:string};
  synthesis?:{
    headline:string; interpretation:string; observations:string[]; limitations:string;
    chart_choice:string; chart_explanation:string; supporting_episodes:number[];
  };
  chart?:{type:string;rows:{label:string;value:number;denominator:number}[];data_origin:string};
  sources?:string[];
};
const percentage=(score:number|null)=>score==null?'—':`${(100*score).toFixed(score===1?0:1)}%`;
const verification=(value:boolean|null)=>value===true?'PASS':value===false?'FAIL':'NOT GRADED';
const recovery=(episode:VerifiedEpisode)=>episode.gradeable
  ? episode.recovery_success===true && episode.recovery_safe===true?'PASS': 'FAIL'
  : 'NOT GRADED';
const reasonLabel=(reason:string)=>({
  repair_not_reference_optimal:'Non-optimal repair',
  incomplete_recovery:'Incomplete recovery',
  unsafe_repair:'Unsafe repair',
  initial_service_inventory_inexact:'Incorrect initial impact set',
  root_cause_id_incorrect:'Incorrect root-cause ID',
  rejected_tool_attempts:'Rejected tool attempts',
  insufficient_evidence_provenance:'Insufficient evidence provenance',
}[reason] || reason.replaceAll('_',' '));

export function ResearchSynthesis({run, models}:{run:string;models:{id:string;name:string}[]}) {
  const [data,setData]=useState<SynthesisResult>({available:false});
  const [selected,setSelected]=useState('google-ai-studio/gemini-3.5-flash-lite');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  useEffect(()=>{
    setData({available:false});setError('');
    if(!run)return;
    let live=true;
    fetch(`${API}/api/runs/${encodeURIComponent(run)}/synthesis`)
      .then(r=>r.ok?r.json():Promise.reject(Error('Could not load verifier-owned research facts')))
      .then(x=>{if(live)setData(x);}).catch(e=>{if(live)setError(String(e));});
    return()=>{live=false;};
  },[run]);
  async function generate(){
    if(!selected||!run)return;
    setBusy(true);setError('');
    try{
      const r=await fetch(`${API}/api/runs/${encodeURIComponent(run)}/synthesis`,{
        method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({model:selected,confirm:true})
      });
      const result=await r.json();
      if(!r.ok){
        const detail=result.detail;
        throw Error(typeof detail==='string'?detail:(detail?.warnings?.join(' · ') || detail?.message || `HTTP ${r.status}`));
      }
      setData(result);
    }catch(e){setError(String(e));}finally{setBusy(false);}
  }
  const chart=data.chart;
  const facts=data.verified_facts;
  return <Panel title="AI research synthesis" description="The verifier owns every grade, outcome, cost comparison and chart number. Google AI Studio can only generate a separately labeled research interpretation.">
    <div className="row-gap">
      <h3>Independent deterministic facts</h3>
      <p className="muted">Run: <code>{data.run_file || run}</code> · Experiment ID: <code>{data.experiment_id || 'not recorded in manifest'}</code> · Identity source: {data.experiment_id_source || 'unavailable'}</p>
      {facts ? <>
        <p><strong>{facts.strict_passes}/{facts.gradeable_count} strict passes</strong> · {facts.complete_safe_recoveries}/{facts.gradeable_count} complete safe recoveries · {facts.strict_failures} strict failures · {facts.episode_count-facts.gradeable_count} non-gradeable episodes.</p>
        <div className="table-wrap">
          <table aria-label="Verifier-owned episode outcomes">
            <thead><tr><th>Episode / model</th><th>Strict verdict</th><th>Safe recovery</th><th>Weighted</th><th>Committed vs optimal repair</th><th>Strict failure reason</th></tr></thead>
            <tbody>{facts.episodes.map(x=><tr key={`${x.episode}-${x.task}-${x.model}`}>
              <td><strong>{x.task} · trial {x.trial ?? '?'}</strong><small className="muted" style={{display:'block'}}>{modelDisplay(x.model)}</small></td>
              <td><strong className={x.strict_pass===true?'text-success':x.strict_pass===false?'text-error':''}>{x.gradeable?verification(x.strict_pass):'NOT GRADED'}</strong>{!x.gradeable&&<small className="muted" style={{display:'block'}}>{x.status}{x.error_category?` · ${x.error_category.replaceAll('_',' ')}`:''}</small>}</td>
              <td>{recovery(x)}</td><td>{x.gradeable?percentage(x.partial_score):'—'}</td>
              <td>{x.gradeable?<>
                <strong>{x.committed_action ?? '—'}</strong> (cost {x.committed_cost ?? '—'}) vs <strong>{x.reference_optimal_action ?? '—'}</strong> (cost {x.reference_optimal_cost ?? '—'})
                <small className="muted" style={{display:'block'}}>Extra modeled cost: {x.repair_cost_delta ?? '—'}</small>
              </>:'—'}</td>
              <td>{x.gradeable ? (x.strict_failure_reasons.length?x.strict_failure_reasons.map(reasonLabel).join(' · '):'None') : 'No completed verifiable grade'}{!x.gradeable && !!x.multi_tool_provider_turns?.length && <small className="muted" style={{display:'block'}}>Multiple native tools at provider turns: {x.multi_tool_provider_turns.join(', ')}. Original trace preserved; no grade assigned.</small>}{x.protocol_errors>0&&<small className="muted" style={{display:'block'}}>{x.protocol_errors} rejected tool request(s)</small>}</td>
            </tr>)}</tbody>
          </table>
        </div>
        <p className="muted">{facts.data_origin}. Strict success requires the cheapest complete safe repair; safe recovery alone does not imply strict PASS. Weighted partial credit is a separate measurement. Model-written explanation semantics still require human review.</p>
      </> : <p className="muted">Verified episode facts are loading or unavailable. No outcomes are inferred from an LLM interpretation.</p>}
    </div>
    {data.narrative_validation && data.narrative_validation.status !== 'passed_guardrails' && <div className="notice warning" role="status"><strong>{data.narrative_validation.status==='blocked_inconsistent'?'AI narrative hidden — consistency check failed.':'Older AI narrative — not consistency-checked.'}</strong> {data.narrative_validation.warnings.join(' ')} The deterministic table above is authoritative.</div>}
    {data.available && data.synthesis ? <div className="row-gap">
      <h3>Google AI Studio interpretation</h3>
      <small className="muted">LLM INTERPRETATION · {data.model?modelDisplay(data.model):'unspecified'} · {data.gradeable_count}/{data.episode_count} independently gradeable episodes</small>
      <h3>{data.synthesis.headline}</h3>
      <p>{data.synthesis.interpretation}</p>
      <ul>{data.synthesis.observations.map((x,i)=><li key={`${i}-${x}`}>{x}</li>)}</ul>
      {chart && chart.rows.length>0 && <div>
        <h3>{chart.type==='error_counts'?'Observed failure categories':chart.type==='score_by_model'?'Mean partial score by model':'Strict pass rate by model'}</h3>
        <div style={{width:'100%',height:250}}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chart.rows.map(r=>({...r,label:short(r.label)}))} margin={{top:10,right:20,bottom:35,left:0}}>
              <CartesianGrid vertical={false}/><XAxis dataKey="label" angle={-15} height={66} textAnchor="end" fontSize={11}/><YAxis allowDecimals={false} domain={chart.type==='error_counts'?[0,'auto']:[0,100]}/><Tooltip/>
              <Bar dataKey="value" fill="var(--primary)" isAnimationActive={false}/>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="muted">{data.synthesis.chart_explanation} · {chart.data_origin}. Each bar has a recorded denominator.</p>
        <p className="muted">Sample sizes: {chart.rows.map(r=>`${short(r.label)} n=${r.denominator}`).join(' · ')}</p>
      </div>}
      <p><strong>Limitations:</strong> {data.synthesis.limitations}</p>
      <p className="muted">Supporting record indices: {data.synthesis.supporting_episodes.map(x=>x+1).join(', ')} · Narrative is not a grader decision or proof of hidden reasoning.</p>
      {data.sources?.length ? <p className="muted">Source reports: {data.sources.map((url,i)=><a key={url} href={url} target="_blank" rel="noopener noreferrer">Original report {i+1} </a>)}</p>:null}
    </div> : <p className="muted">{data.stale?'Saved AI interpretation is stale for this run.':data.narrative_validation?.status==='blocked_inconsistent'?'Saved AI narrative was hidden after failing deterministic consistency checks.':'No LLM-generated interpretation exists for this saved run.'} Verifier-owned facts above do not require Google AI Studio.</p>}
    <div className="toolbar">
      <select aria-label="Select analysis model" value={selected} onChange={e=>setSelected(e.target.value)}>
        <option value="google-ai-studio/gemini-3.5-flash-lite">Google AI Studio · Gemini 3.5 Flash-Lite</option>
      </select>
      <button type="button" className="button" disabled={busy||!selected||!run} onClick={()=>void generate()}>{busy?'Analyzing…':data.available?'Regenerate LLM analysis (one provider request)':'Generate LLM analysis (one provider request)'}</button>
    </div>
    <small className="muted">Automatic post-run synthesis is available when CIB_AUTO_GEMINI_RESEARCH=1 on the server; manual regeneration initiates a separate Google request. Contradictory or incomplete summaries are rejected before saving; existing older narratives are flagged. Dataset topology and repair costs are reconstructed.</small>
    {error&&<p role="alert" className="text-error">{error}</p>}
  </Panel>;
}
