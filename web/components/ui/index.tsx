'use client';
import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  CloudOff,
  Download,
  Minus,
  TriangleAlert,
  X
} from 'lucide-react';
import { API } from '../../lib/api';
import type { EvidenceRow, Task } from '../../lib/api';
import { p100, short, statusLabel } from '../../lib/presentation';
export function Status({ value }: { value: string }) {
  const cls = ['completed', 'finished', 'passed'].includes(value)
    ? 'good'
    : ['error', 'failed'].includes(value)
      ? 'bad'
      : ['incomplete_generation', 'empty_generation', 'unverified', 'running', 'stopping'].includes(
            value,
          )
        ? 'warn'
        : 'neutral';
  return (
    <span className={`badge ${cls}`}>
      {cls === 'good' ? (
        <Check size={12} />
      ) : cls === 'bad' ? (
        <X size={12} />
      ) : cls === 'warn' ? (
        <TriangleAlert size={12} />
      ) : (
        <Minus size={12} />
      )}{' '}
      {statusLabel(value)}
    </span>
  );
}
export function Panel({
  title,
  description,
  children,
  side,
  footer,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  side?: React.ReactNode;
  footer?: React.ReactNode;
}) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>{title}</h2>
          {description && <p>{description}</p>}
        </div>
        {side}
      </div>
      <div className="panel-content">{children}</div>
      {footer && <div className="panel-footer">{footer}</div>}
    </section>
  );
}
export function Empty({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="empty">
      <CloudOff size={24} />
      <strong>{title}</strong>
      {detail && <p>{detail}</p>}
    </div>
  );
}
export function Json({ value }: { value: unknown }) {
  return <pre className="block-code">{JSON.stringify(value, null, 2)}</pre>;
}
export function Code({ value }: { value: unknown }) {
  const content = typeof value === 'string' ? value : JSON.stringify(value, null, 2);
  return (
    <div className="block-code mono">
      {content.split('\n').map((line, i) => (
        <div className="code-line" key={i}>
          <span className="ln">{i + 1}</span>
          <span>{line || ' '}</span>
        </div>
      ))}
    </div>
  );
}
export function Figure({ children, caption }: { children: React.ReactNode; caption: string }) {
  return (
    <>
      <div className="chart">{children}</div>
      <div className="fig-caption">{caption}</div>
    </>
  );
}
/** Exact service tiles derived from the loaded deterministic oracle, never invented counts. */
export function IncidentStateStrip({
  title, services, unavailable, caption,
}: {
  title: string;
  services: string[];
  unavailable: string[];
  caption: string;
}) {
  const down = new Set(unavailable);
  return (
    <div className="research-state-card">
      <span className="research-eyebrow">{title}</span>
      <div className="research-state-value">{unavailable.length} down <small>/ {services.length} services</small></div>
      <div className="research-service-cells" role="img" aria-label={`${unavailable.length} of ${services.length} services unavailable`}>
        {services.map((name) => (
          <span key={name} title={`${name}: ${down.has(name) ? 'unavailable' : 'healthy'}`} className={down.has(name) ? 'service-cell-down' : 'service-cell-up'}/>
        ))}
      </div>
      <p className="muted">{caption}</p>
    </div>
  );
}
export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="field-group">
      <label>{label}</label>
      {children}
    </div>
  );
}
export function Metric({
  label,
  value,
  caption,
  onClick,
}: {
  label: string;
  value: string | number;
  caption: string;
  onClick?: () => void;
}) {
  return (
    <div
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onClick={onClick}
      onKeyDown={(e) => {
        if (onClick && (e.key === 'Enter' || e.key === ' ')) onClick();
      }}
      className={`stat ${onClick ? 'link' : ''} ${['Exact pass rate', 'Mean partial score'].includes(label) ? 'featured' : ''}`}
    >
      <label>{label}</label>
      <strong>{value}</strong>
      <small>{caption}</small>
    </div>
  );
}
export function Tabs({
  values,
  value,
  onChange,
}: {
  values: string[];
  value: string;
  onChange: (t: string) => void;
}) {
  return (
    <div className="tabs" role="tablist">
      {values.map((t) => (
        <button
          type="button"
          key={t}
          role="tab"
          aria-selected={t === value}
          className={`tab ${t === value ? 'selected' : ''}`}
          onClick={() => onChange(t)}
        >
          {t}
        </button>
      ))}
    </div>
  );
}
export function DownloadLink({ href, label }: { href: string; label: string }) {
  return (
    <a className="button" href={`${API}${href}`} download>
      <Download size={15} />
      {label}
    </a>
  );
}
export function Integrity({
  label,
  status,
  detail,
}: {
  label: string;
  status: 'pass' | 'fail' | 'warning';
  detail?: string;
}) {
  return (
    <div className="integrity-item">
      <span
        className={
          status === 'pass' ? 'text-success' : status === 'fail' ? 'text-error' : 'text-warning'
        }
      >
        {status === 'pass' ? <CheckCircle size={18} /> : <AlertTriangle size={18} />}
      </span>
      <span>
        {label}
        {detail && <small style={{ display: 'block' }}>{detail}</small>}
      </span>
      <Status value={status === 'pass' ? 'passed' : status === 'fail' ? 'failed' : 'unverified'} />
    </div>
  );
}
export function Table({
  rows,
  onSelect,
}: {
  rows: (EvidenceRow & {
    index: number;
  })[];
  onSelect: (index: number) => void;
}) {
  const [sort, setSort] = useState<'task' | 'model' | 'score'>('task');
  const [ascending, setAscending] = useState(true);
  const [page, setPage] = useState(0);
  const [compact, setCompact] = useState(false);
  const ordered = useMemo(
    () =>
      [...rows].sort((a, b) => {
        const av = sort === 'score' ? (a.score ?? -1) : String(a[sort]);
        const bv = sort === 'score' ? (b.score ?? -1) : String(b[sort]);
        const d =
          typeof av === 'number' && typeof bv === 'number'
            ? av - bv
            : String(av).localeCompare(String(bv));
        return ascending ? d : -d;
      }),
    [rows, sort, ascending],
  );
  const order = (key: typeof sort) => {
    setPage(0);
    if (key === sort) setAscending((v) => !v);
    else {
      setSort(key);
      setAscending(true);
    }
  };
  const last = Math.max(0, Math.ceil(ordered.length / 10) - 1);
  const current = Math.min(page, last);
  return (
    <>
      <div className="toolbar">
        <span className="muted">
          {ordered.length} records · page {current + 1} of {last + 1}
        </span>
        <div className="grow" />
        <label>
          <input type="checkbox" checked={compact} onChange={(e) => setCompact(e.target.checked)} />{' '}
          Compact columns
        </label>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>
                <button className="button" onClick={() => order('task')}>
                  Task
                </button>
              </th>
              <th>
                <button className="button" onClick={() => order('model')}>
                  Model
                </button>
              </th>
              <th>Trial</th>
              <th>Status</th>
              <th className="num">
                <button className="button" onClick={() => order('score')}>
                  Score
                </button>
              </th>
              {!compact && (
                <>
                  <th>Root</th>
                  <th>Repair</th>
                </>
              )}
              <th>Evidence</th>
            </tr>
          </thead>
          <tbody>
            {ordered.slice(current * 10, current * 10 + 10).map((r) => (
              <tr
                className="clickable"
                tabIndex={0}
                key={r.index}
                onClick={() => onSelect(r.index)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') onSelect(r.index);
                }}
              >
                <td className="mono">{r.task}</td>
                <td title={r.model}>{short(r.model)}</td>
                <td>{r.trial}</td>
                <td>
                  <Status value={r.status} />
                </td>
                <td className="num">{p100(r.score)}</td>
                {!compact && (
                  <>
                    <td>
                      {r.root_correct == null ? '—' : r.root_correct ? 'Correct' : 'Incorrect'}
                    </td>
                    <td>{r.fix_correct == null ? '—' : r.fix_correct ? 'Correct' : 'Incorrect'}</td>
                  </>
                )}
                <td>
                  <button
                    className="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelect(r.index);
                    }}
                  >
                    Open <ArrowRight size={13} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!ordered.length && (
          <Empty
            title="No matching records"
            detail="Choose a completed run or change the filter."
          />
        )}
      </div>
      <div className="toolbar" style={{ justifyContent: 'flex-end', marginTop: 12 }}>
        <button className="button" disabled={current <= 0} onClick={() => setPage(current - 1)}>
          <ChevronLeft size={16} />
          Previous
        </button>
        <button className="button" disabled={current >= last} onClick={() => setPage(current + 1)}>
          Next <ChevronRight size={16} />
        </button>
      </div>
    </>
  );
}
