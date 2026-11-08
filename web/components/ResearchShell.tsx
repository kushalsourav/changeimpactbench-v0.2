'use client';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  CloudOff,
  GitBranch,
  Info,
  Menu,
  RefreshCw,
  Search,
  Sun,
  Moon,
  X
} from 'lucide-react';
import { NAV, desc, runLabel } from '../lib/presentation';
import { useWorkbenchState } from '../store/WorkbenchContext';
import { Overview } from '../pages/Overview';
import { ControlRoom } from '../pages/ControlRoom';
import { ExecutionAnalysis } from '../pages/ExecutionAnalysis';
export function ResearchShell() {
  const { page, setPage, collapsed, setCollapsed, dark, setDark, health, runs, run, setRun, info, task, setRecordIndex, trial, setTrial, setAnalysisTab, loading, error, setError, search, setSearch, setFilter, flowNotice, setFlowNotice, selectPage, refreshRuns, refreshRun, selected, explanation } = useWorkbenchState();
  return (
    <div className="shell">
      <aside className={`rail ${collapsed ? 'collapsed' : ''}`}>
        <div className="brand">
          <div className="brand-symbol">
            <GitBranch size={20} />
          </div>
          <div className="brand-copy">
            <strong>ChangeImpactBench</strong>
            <small>AI incident evaluation</small>
          </div>
        </div>
        <nav aria-label="Main navigation" className="nav">
          {NAV.map((n) => {
            const Icon = n.icon;
            return (
              <button
                title={n.label}
                aria-current={page === n.id ? 'page' : undefined}
                className={`nav-item ${page === n.id ? 'selected' : ''}`}
                onClick={() => selectPage(n.id)}
                                key={n.id}
              >
                <Icon size={18} />
                <span className="nav-label">
                  {n.label}
                  
                </span>
              </button>
            );
          })}
        </nav>
        <div className="rail-footer">
          <span className={health ? 'text-success' : 'text-error'}>
            {health ? <CheckCircle size={17} /> : <CloudOff size={17} />}
          </span>
          <span>{health ? 'FastAPI connected' : 'Backend unavailable'}</span>
          <button
            className="icon-btn"
            title={collapsed ? 'Expand navigation' : 'Collapse navigation'}
            onClick={() => setCollapsed((v) => !v)}
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>
      </aside>
      <main className="workspace">
        <header className="appbar">
          <button
            className="icon-btn"
            aria-label="Toggle navigation"
            onClick={() => setCollapsed((v) => !v)}
          >
            <Menu size={18} />
          </button>
          <strong className="appbar-context">ChangeImpactBench / {page === 'analysis' ? 'Results / Evidence' : NAV.find((item) => item.id === page)?.label}</strong>
          <div className="grow" />
          {page !== 'control' && <div className="appbar-search">
            <Search size={15} />
            <input
              aria-label="Search evidence"
              placeholder="Find model, trial, incident"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') { setFilter(search); setAnalysisTab('Summary'); setPage('analysis'); }
              }}
            />
          </div>}
          {page !== 'control' && <select
            aria-label="Select experiment"
            value={run}
            onChange={(e) => {
              setRun(e.target.value);
              setRecordIndex(0);
              setTrial(null);
            }}
          >
            <option value="">Choose an experiment</option>
            {runs.map((r) => (
              <option key={r.name} value={r.name} title={r.name}>
                {runLabel(r)}
              </option>
            ))}
          </select>}
          {page !== 'control' && <button
            title="Reload evidence"
            className="icon-btn"
            onClick={() => {
              refreshRuns();
              refreshRun();
            }}
          >
            <RefreshCw size={16} />
          </button>}
          <button title="Toggle theme" className="icon-btn" onClick={() => setDark((v) => !v)}>
            {dark ? <Sun size={17} /> : <Moon size={17} />}
          </button>
        </header>
        <nav className="mobile-menu" aria-label="Mobile navigation">
          {NAV.map((n) => (
            <button
              key={n.id}
              className={`button ${page === n.id ? 'primary' : ''}`}
              onClick={() => setPage(n.id)}
            >
              {n.label}
            </button>
          ))}
        </nav>
        <div className="page">
          {page === 'analysis' && (
            <div className="page-heading simple-evidence-heading">
              <div>
                <button className="text-link-action" onClick={() => setPage('overview')}>
                  <ChevronLeft size={14} /> Back to Results
                </button>
                <h1>Episode evidence</h1>
                <p>See what the model did and why it passed or failed.</p>
              </div>
            </div>
          )}
          {flowNotice && (
            <div className="notice" role="status">
              <CheckCircle size={16} />
              <span style={{ flex: 1 }}>{flowNotice}</span>
              <button
                className="button"
                onClick={() => {
                  setAnalysisTab('Summary');
                  setPage('analysis');
                  setFlowNotice('');
                }}
              >
                View explanation <ArrowRight size={13} />
              </button>
              <button
                className="button"
                aria-label="Dismiss notification"
                onClick={() => setFlowNotice('')}
              >
                <X size={13} />
              </button>
            </div>
          )}
          {error && (
            <div role="alert" className="notice error">
              <AlertTriangle size={18} />
              <span style={{ flex: 1 }}>{error}</span>
              <button className="button" onClick={() => setError('')}>
                Dismiss
              </button>
            </div>
          )}
          {!health && (
            <div className="notice warning">
              <CloudOff size={18} />
              FastAPI is not connected. Start the backend on 127.0.0.1:8000, then reload.
            </div>
          )}
          {loading && (
            <div role="status" className="notice">
              <Info size={16} />
              Loading saved records from FastAPI.
            </div>
          )}
          {page === 'overview' && <Overview />}
          {page === 'analysis' && <ExecutionAnalysis />}
          {page === 'control' && <ControlRoom />}
        </div>
      </main>
    </div>
  );
}
