'use client';
import { AlertTriangle, ArrowRight, CheckCircle, ChevronLeft, CloudOff, RefreshCw, Search, X } from 'lucide-react';
import { NAV, runLabel } from '../lib/presentation';
import { useWorkbenchState } from '../store/WorkbenchContext';
import { Overview } from '../pages/Overview';
import { ControlRoom } from '../pages/ControlRoom';
import { ExecutionAnalysis } from '../pages/ExecutionAnalysis';

/** Compact two-page shell. Technical evidence is a detail view of Results. */
export function ResearchShell() {
  const {
    page, setPage, health, runs, run, setRun, setRecordIndex, setTrial,
    setAnalysisTab, loading, error, setError, search, setSearch,
    flowNotice, setFlowNotice, refreshRuns, refreshRun, job,
  } = useWorkbenchState();
  return <div className="shell cib-shell">
    <main className="workspace cib-workspace">
      <header className="appbar cib-appbar">
        <strong className="cib-logo">ChangeImpactBench</strong>
        <span className="cib-divider">/</span>
        <nav className="cib-nav" aria-label="Main navigation">
          {NAV.map(item => <button key={item.id}
            className={`cib-nav-link ${page === item.id || (page === 'analysis' && item.id === 'overview') ? 'active' : ''}`}
            aria-current={page === item.id ? 'page' : undefined}
            onClick={() => setPage(item.id)}>{item.label}</button>)}
        </nav>
        <div className="grow"/>
        {job.status === 'running' || job.status === 'stopping'
          ? <span className="cib-connection active" role="status">● Live</span>
          : <span className="cib-connection" role="status">{health ? '● Ready' : '○ Offline'}</span>}
        {page !== 'control' && <div className="appbar-search cib-search">
          <Search size={14}/>
          <input aria-label="Search saved investigations" placeholder="Find model, trial, incident"
            value={search} onChange={e => setSearch(e.target.value)}/>
        </div>}
        {page !== 'control' && <select className="cib-run-select" aria-label="Select saved experiment"
          value={run} onChange={e => { setRun(e.target.value); setRecordIndex(0); setTrial(null); }}>
          <option value="">Choose an experiment</option>
          {runs.map(r => <option key={r.name} value={r.name} title={r.name}>{runLabel(r)}</option>)}
        </select>}
        {page !== 'control' && <button className="icon-btn" title="Reload saved results"
          onClick={() => { void refreshRuns(); void refreshRun(); }}><RefreshCw size={16}/></button>}
      </header>
      <div className="page cib-page">
        {page === 'analysis' && <div className="cib-evidence-back">
          <button className="text-link-action" onClick={() => setPage('overview')}><ChevronLeft size={14}/>Back to Results</button>
          <h1>Episode evidence</h1>
        </div>}
        {flowNotice && page !== 'control' && <div className="notice" role="status">
          <CheckCircle size={16}/><span style={{flex:1}}>{flowNotice}</span>
          <button className="button" onClick={() => { setPage('analysis'); setAnalysisTab('Summary'); setFlowNotice(''); }}>
            View evidence <ArrowRight size={13}/></button>
          <button className="icon-btn" aria-label="Dismiss notification" onClick={() => setFlowNotice('')}><X size={14}/></button>
        </div>}
        {error && <div role="alert" className="notice error"><AlertTriangle size={16}/>
          <span style={{flex:1}}>{error}</span>
          <button className="button" onClick={() => setError('')}>Dismiss</button></div>}
        {!health && <div className="notice warning"><CloudOff size={16}/>Backend unavailable. Start FastAPI, then refresh.</div>}
        {loading && page !== 'control' && <div className="notice" role="status">Loading results…</div>}
        {page === 'control' && <ControlRoom/>}
        {page === 'overview' && <Overview/>}
        {page === 'analysis' && <ExecutionAnalysis/>}
      </div>
    </main>
  </div>;
}
