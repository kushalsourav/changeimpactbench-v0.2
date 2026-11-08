'use client';
import { useMemo, useState } from 'react';
import { Maximize, ZoomIn, ZoomOut } from 'lucide-react';
import type { NodeInfo } from '../lib/api';
import type { LiveNodeObservation } from '../lib/live-observations';

type Health = 'unknown' | 'healthy' | 'failed' | 'downstream' | 'restored' | 'newly-damaged';
type Point = { x: number; y: number };
type DrawNode = NodeInfo & { status: Health; selected: boolean; detail: string; evidence: string };
type DrawEdge = {
  id: string;
  source: string;
  target: string;
  kind: 'required' | 'redundant' | 'quorum';
  failed: boolean;
  label?: string;
};

const NODE_WIDTH = 170;
const NODE_HEIGHT = 64;
const COLUMN_GAP = 58;
const ROW_GAP = 22;
const PAD = 18;

function mappedNode(node: NodeInfo, serviceCodes?: Record<string, string>): NodeInfo {
  const code = (id: string) => serviceCodes?.[id] || id;
  return {
    id: code(node.id),
    needs_all: node.needs_all.map(code),
    needs_any: node.needs_any.map(code),
    needs_at_least: node.needs_at_least
      ? { count: node.needs_at_least.count, of: node.needs_at_least.of.map(code) }
      : undefined,
  };
}

/** Deterministic SVG layout adapted from demo.html; it cannot initialize to a blank viewport. */
function buildLayout(nodes: NodeInfo[]) {
  const parents: Record<string, string[]> = Object.fromEntries(nodes.map((node) => [node.id, []]));
  const connected = new Set<string>();
  const edges: Omit<DrawEdge, 'failed'>[] = [];
  const add = (source: string, target: string, kind: DrawEdge['kind'], label?: string) => {
    if (!parents[target] || !parents[source]) return;
    const id = `${source}->${target}:${kind}`;
    if (edges.some((edge) => edge.id === id)) return;
    edges.push({ id, source, target, kind, label });
    parents[target].push(source);
    connected.add(source);
    connected.add(target);
  };
  for (const node of nodes) {
    node.needs_all.forEach((source) => add(source, node.id, 'required'));
    node.needs_any.forEach((source) => add(source, node.id, 'redundant'));
    node.needs_at_least?.of.forEach((source) =>
      add(
        source,
        node.id,
        'quorum',
        `${node.needs_at_least?.count}/${node.needs_at_least?.of.length}`,
      ),
    );
  }

  const depths: Record<string, number> = Object.fromEntries(nodes.map((node) => [node.id, 0]));
  // The fixtures are DAGs. The bounded loop also keeps malformed/cyclic input finite.
  for (let pass = 0; pass < nodes.length; pass++) {
    let changed = false;
    for (const node of nodes) {
      if (!connected.has(node.id)) continue;
      const next = parents[node.id].length
        ? Math.min(nodes.length - 1, Math.max(...parents[node.id].map((id) => depths[id] || 0)) + 1)
        : 0;
      if (next > depths[node.id]) {
        depths[node.id] = next;
        changed = true;
      }
    }
    if (!changed) break;
  }

  const layers: Record<number, string[]> = {};
  nodes
    .filter((node) => connected.has(node.id))
    .forEach((node) => (layers[depths[node.id]] ??= []).push(node.id));
  Object.values(layers).forEach((layer) => layer.sort());
  const layerValues = Object.entries(layers).sort(([a], [b]) => Number(a) - Number(b));
  const mainRows = Math.max(1, ...layerValues.map(([, layer]) => layer.length));
  const mainHeight = Math.max(300, mainRows * (NODE_HEIGHT + ROW_GAP) - ROW_GAP);
  const positions: Record<string, Point> = {};
  for (const [depthText, layer] of layerValues) {
    const depth = Number(depthText);
    const usedHeight = layer.length * (NODE_HEIGHT + ROW_GAP) - ROW_GAP;
    const offset = PAD + Math.max(0, (mainHeight - usedHeight) / 2);
    layer.forEach((id, index) => {
      positions[id] = {
        x: PAD + depth * (NODE_WIDTH + COLUMN_GAP),
        y: offset + index * (NODE_HEIGHT + ROW_GAP),
      };
    });
  }

  const isolated = nodes
    .filter((node) => !connected.has(node.id))
    .map((node) => node.id)
    .sort();
  const isolationY = PAD + mainHeight + (isolated.length ? 34 : 0);
  isolated.forEach((id, index) => {
    positions[id] = { x: PAD + index * (NODE_WIDTH + COLUMN_GAP), y: isolationY };
  });
  const columnCount = Math.max(1, layerValues.length, isolated.length);
  const width = PAD * 2 + columnCount * NODE_WIDTH + Math.max(0, columnCount - 1) * COLUMN_GAP;
  const height = isolationY + (isolated.length ? NODE_HEIGHT : 0) + PAD;
  return { positions, edges, width, height };
}

export function Topology({
  nodes,
  failed,
  predicted,
  directFailed,
  selected,
  onSelect,
  before,
  unknown,
  observedHealth,
  serviceCodes,
  nodeObservations,
}: {
  nodes: NodeInfo[];
  failed: string[];
  predicted?: string[];
  directFailed?: string[];
  selected?: string;
  onSelect?: (id: string) => void;
  before?: string[];
  unknown?: boolean;
  observedHealth?: Record<string, 'healthy' | 'unavailable'>;
  serviceCodes?: Record<string, string>;
  nodeObservations?: Record<string, LiveNodeObservation>;
}) {
  const [zoom, setZoom] = useState(1);
  const graph = useMemo(() => {
    const mapped = nodes.map((node) => mappedNode(node, serviceCodes));
    const layout = buildLayout(mapped);
    const down = new Set(failed.map((id) => serviceCodes?.[id] || id));
    const direct = new Set((directFailed || []).map((id) => serviceCodes?.[id] || id));
    const original = new Set((before || failed).map((id) => serviceCodes?.[id] || id));
    const predictedDown = new Set((predicted || []).map((id) => serviceCodes?.[id] || id));
    const drawNodes: DrawNode[] = mapped.map((node) => {
      const now = down.has(node.id),
        prior = original.has(node.id);
      const observation = observedHealth?.[node.id];
      const status: Health = observedHealth
        ? observation === 'healthy'
          ? 'healthy'
          : observation === 'unavailable'
            ? 'failed'
            : 'unknown'
        : unknown
          ? 'unknown'
          : now
            ? !prior
              ? 'newly-damaged'
              : direct.has(node.id)
                ? 'failed'
                : 'downstream'
            : prior
              ? 'restored'
              : 'healthy';
      return {
        ...node,
        status,
        selected: selected === node.id || serviceCodes?.[selected || ''] === node.id,
        detail:
          nodeObservations?.[node.id]?.config || nodeObservations?.[node.id]?.dependencies || '',
        evidence: [nodeObservations?.[node.id]?.config, nodeObservations?.[node.id]?.dependencies]
          .filter(Boolean)
          .join('. '),
      };
    });
    const drawEdges: DrawEdge[] = layout.edges.map((edge) => ({
      ...edge,
      failed: observedHealth
        ? observedHealth[edge.source] === 'unavailable' &&
          observedHealth[edge.target] === 'unavailable'
        : down.has(edge.source) && down.has(edge.target),
    }));
    return {
      ...layout,
      nodes: drawNodes,
      edges: drawEdges,
      disagreements: predicted
        ? mapped.filter((node) => down.has(node.id) !== predictedDown.has(node.id)).length
        : 0,
    };
  }, [
    nodes,
    serviceCodes,
    failed,
    directFailed,
    before,
    predicted,
    observedHealth,
    nodeObservations,
    unknown,
    selected,
  ]);

  const viewWidth = graph.width / zoom;
  const viewHeight = graph.height / zoom;
  const viewX = (graph.width - viewWidth) / 2;
  const viewY = (graph.height - viewHeight) / 2;
  const statusText = (node: DrawNode) => {
    if (node.needs_at_least && node.status === 'failed')
      return `unavailable · quorum ${node.needs_at_least.count} of ${node.needs_at_least.of.length}`;
    return node.status === 'failed'
      ? 'unavailable'
      : node.status === 'healthy'
        ? 'healthy'
        : node.status === 'unknown'
          ? 'not checked'
          : node.status.replace('-', ' ');
  };

  return (
    <div className="topology-shell cib-svg-topology">
      <div className="graph-actions">
        <button
          className="icon-btn"
          aria-label="Zoom in"
          disabled={zoom >= 1.8}
          onClick={() => setZoom((value) => Math.min(1.8, value + 0.2))}
        >
          <ZoomIn size={17} />
        </button>
        <button
          className="icon-btn"
          aria-label="Zoom out"
          disabled={zoom <= 0.6}
          onClick={() => setZoom((value) => Math.max(0.6, value - 0.2))}
        >
          <ZoomOut size={17} />
        </button>
        <button className="icon-btn" aria-label="Fit graph" onClick={() => setZoom(1)}>
          <Maximize size={17} />
        </button>
      </div>
      <svg
        className="topology-svg"
        viewBox={`${viewX} ${viewY} ${viewWidth} ${viewHeight}`}
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={`Service dependency graph with ${graph.nodes.length} services`}
      >
        <defs>
          <pattern id="topology-grid" width="24" height="24" patternUnits="userSpaceOnUse">
            <circle cx="1" cy="1" r="1" className="topology-grid-dot" />
          </pattern>
          <marker
            id="topology-arrow"
            viewBox="0 0 8 8"
            refX="7"
            refY="4"
            markerWidth="7"
            markerHeight="7"
            orient="auto"
          >
            <path d="M0,0 L8,4 L0,8 z" className="topology-arrow" />
          </marker>
        </defs>
        <rect x="0" y="0" width={graph.width} height={graph.height} fill="url(#topology-grid)" />
        {graph.edges.map((edge) => {
          const from = graph.positions[edge.source],
            to = graph.positions[edge.target];
          if (!from || !to) return null;
          const x1 = from.x + NODE_WIDTH,
            y1 = from.y + NODE_HEIGHT / 2;
          const x2 = to.x,
            y2 = to.y + NODE_HEIGHT / 2;
          const curve = Math.max(24, Math.abs(x2 - x1) / 2);
          return (
            <g key={edge.id}>
              <path
                className={`topology-edge topology-edge-${edge.kind}${edge.failed ? ' failed' : ''}`}
                d={`M${x1},${y1} C${x1 + curve},${y1} ${x2 - curve},${y2} ${x2},${y2}`}
                markerEnd="url(#topology-arrow)"
              />
              {edge.label && (
                <text className="topology-edge-label" x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 5}>
                  {edge.label}
                </text>
              )}
            </g>
          );
        })}
        {graph.nodes.map((node) => {
          const point = graph.positions[node.id];
          if (!point) return null;
          return (
            <g
              key={node.id}
              className={`topology-node topology-node-${node.status}${node.evidence ? ' inspected' : ''}${node.selected ? ' selected' : ''}`}
              role={onSelect ? 'button' : undefined}
              tabIndex={onSelect ? 0 : undefined}
              onClick={() => onSelect?.(node.id)}
              onKeyDown={(event) => {
                if (onSelect && (event.key === 'Enter' || event.key === ' ')) onSelect(node.id);
              }}
            >
              <title>{`${node.id}: ${statusText(node)}${node.evidence ? `. ${node.evidence}` : ''}`}</title>
              {node.selected && (
                <rect
                  className="topology-node-focus"
                  x={point.x - 4}
                  y={point.y - 4}
                  width={NODE_WIDTH + 8}
                  height={NODE_HEIGHT + 8}
                  rx="10"
                />
              )}
              <rect
                className="topology-node-box"
                x={point.x}
                y={point.y}
                width={NODE_WIDTH}
                height={NODE_HEIGHT}
                rx="7"
              />
              <text className="topology-node-name" x={point.x + 10} y={point.y + 20}>
                {node.id}
              </text>
              <text className="topology-node-status" x={point.x + 10} y={point.y + 36}>
                {statusText(node)}
              </text>
              {node.detail && (
                <text className="topology-node-detail" x={point.x + 10} y={point.y + 52}>
                  {node.detail.length > 27 ? `${node.detail.slice(0, 26)}…` : node.detail}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <div className="legend">
        {observedHealth ? (
          <>
            <span>○ Not checked</span>
            <span>✓ Observed healthy</span>
            <span>× Observed unavailable</span>
          </>
        ) : unknown ? (
          <span>○ Status not shown during investigation</span>
        ) : (
          <span>✓ Healthy / restored</span>
        )}
        {!unknown && !observedHealth && (
          <>
            <span>× Failed</span>
            <span>↓ Downstream</span>
            <span>! Newly damaged</span>
          </>
        )}
        <span>─ Required edge</span>
        <span>┄ Redundant edge</span>
        <span>·· Quorum (N of M) edge</span>
        {predicted && <span>Prediction disagreements: {graph.disagreements}</span>}
      </div>
    </div>
  );
}
