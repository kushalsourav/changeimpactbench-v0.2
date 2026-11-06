'use client';
import { useMemo, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Handle,
  Position,
  MarkerType,
  ReactFlowProvider,
  useReactFlow,
  type NodeProps,
  type Node,
  type Edge,
} from '@xyflow/react';
import type { NodeInfo } from '../lib/api';
import {
  Check,
  X,
  ArrowDown,
  RotateCcw,
  AlertTriangle,
  Maximize,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';
type Health = 'healthy' | 'failed' | 'downstream' | 'restored' | 'newly-damaged';
type PaperNodeData = Record<string, unknown> & {
  label: string;
  typeName: string;
  status: Health;
  selected: boolean;
};
const icons = {
  healthy: Check,
  failed: X,
  downstream: ArrowDown,
  restored: RotateCcw,
  'newly-damaged': AlertTriangle,
};
function ServiceNode({ data }: NodeProps<Node<PaperNodeData>>) {
  const Icon = icons[data.status] || Check;
  return (
    <div
      className={`service-node ${data.status} ${data.selected ? 'picked' : ''}`}
      title={`${data.label} • ${data.status}`}
    >
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <div className="service-name">
        <Icon size={14} aria-hidden="true" />
        <span>{data.label}</span>
      </div>
      <div className="service-sub">
        {data.typeName} · {data.status.replace('-', ' ')}
      </div>
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  );
}
const nodeTypes = { paper: ServiceNode };
function GraphCore({
  nodes,
  failed,
  predicted,
  directFailed,
  selected,
  onSelect,
  before,
}: {
  nodes: NodeInfo[];
  failed: string[];
  predicted?: string[];
  directFailed?: string[];
  selected?: string;
  onSelect?: (id: string) => void;
  before?: string[];
}) {
  const { fitView, zoomIn, zoomOut } = useReactFlow();
  const graph = useMemo(() => {
    const down = new Set(failed),
      directDown = new Set(directFailed || []),
      original = new Set(before || failed);
    const predictedDown = new Set(predicted || []);
    const depths: Record<string, number> = {};
    nodes.forEach((n) => (depths[n.id] = 0));
    for (let i = 0; i < nodes.length; i++) {
      let changed = false;
      for (const n of nodes) {
        const d = [...n.needs_all, ...n.needs_any, ...(n.needs_at_least?.of ?? [])];
        const next = d.length ? Math.max(...d.map((x) => depths[x] || 0)) + 1 : 0;
        if (next > depths[n.id] && next < nodes.length) {
          depths[n.id] = next;
          changed = true;
        }
      }
      if (!changed) break;
    }
    const layers: Record<number, NodeInfo[]> = {};
    nodes.forEach((n) => (layers[depths[n.id]] ??= []).push(n));
    const layout: Node<PaperNodeData>[] = [];
    for (const [depth, group] of Object.entries(layers))
      group.forEach((n, index) => {
        const now = down.has(n.id),
          prior = original.has(n.id);
        const direct = now && directDown.has(n.id);
        const status: Health = now
          ? !prior
            ? 'newly-damaged'
            : direct
              ? 'failed'
              : 'downstream'
          : prior
            ? 'restored'
            : 'healthy';
        layout.push({
          id: n.id,
          type: 'paper',
          position: { x: Number(depth) * 248, y: index * 104 + Math.max(0, 5 - group.length) * 46 },
          data: {
            label: n.id,
            typeName: n.id.includes('db')
              ? 'Database'
              : n.id.includes('queue')
                ? 'Queue'
                : 'Service',
            status,
            selected: selected === n.id,
          },
          draggable: false,
          selectable: true,
        });
      });
    const edges: Edge[] = [];
    for (const n of nodes) {
      for (const d of n.needs_all) {
        edges.push({
          id: `${d}->${n.id}`,
          source: d,
          target: n.id,
          type: 'step',
          animated: false,
          style: {
            stroke: down.has(d) && down.has(n.id) ? '#D93025' : '#70757A',
            strokeWidth: down.has(d) && down.has(n.id) ? 2 : 1.5,
          },
          markerEnd: { type: MarkerType.ArrowClosed, color: '#70757A' },
        });
      }
      for (const d of n.needs_any) {
        edges.push({
          id: `${d}->${n.id}:any`,
          source: d,
          target: n.id,
          type: 'step',
          animated: false,
          style: { stroke: '#70757A', strokeDasharray: '6 4', strokeWidth: 1.5 },
          markerEnd: { type: MarkerType.ArrowClosed, color: '#70757A' },
        });
      }
      for (const d of n.needs_at_least?.of ?? []) {
        edges.push({
          id: `${d}->${n.id}:quorum`,
          source: d,
          target: n.id,
          type: 'step',
          animated: false,
          label: `${n.needs_at_least?.count}/${n.needs_at_least?.of.length}`,
          style: { stroke: '#70757A', strokeDasharray: '2 5', strokeWidth: 1.5 },
          markerEnd: { type: MarkerType.ArrowClosed, color: '#70757A' },
        });
      }
    }
    return {
      layout,
      edges,
      disagreements: predicted
        ? nodes.filter((n) => down.has(n.id) !== predictedDown.has(n.id)).length
        : 0,
    };
  }, [nodes, failed, directFailed, predicted, selected, before]);
  const fit = useCallback(() => {
    void fitView({ padding: 0.2, duration: 0 });
  }, [fitView]);
  return (
    <div className="topology-shell">
      <div className="graph-actions">
        <button
          className="icon-btn"
          aria-label="Zoom in"
          onClick={() => void zoomIn({ duration: 0 })}
        >
          <ZoomIn size={17} />
        </button>
        <button
          className="icon-btn"
          aria-label="Zoom out"
          onClick={() => void zoomOut({ duration: 0 })}
        >
          <ZoomOut size={17} />
        </button>
        <button className="icon-btn" aria-label="Fit graph" onClick={fit}>
          <Maximize size={17} />
        </button>
      </div>
      <ReactFlow
        nodes={graph.layout}
        edges={graph.edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        elementsSelectable
        onNodeClick={(_, node) => onSelect?.(node.id)}
        zoomOnDoubleClick={false}
        panOnScroll
        zoomOnScroll={false}
        zoomOnPinch
        preventScrolling
        edgesFocusable={false}
        minZoom={0.3}
        maxZoom={2}
      >
        <Background color="#E4E2DC" gap={24} size={1} />
      </ReactFlow>
      <div className="legend">
        <span>✓ Healthy / restored</span>
        <span>× Failed</span>
        <span>↓ Downstream</span>
        <span>! Newly damaged</span>
        <span>─ Required edge</span>
        <span>┄ Redundant edge</span>
        <span>·· Quorum (N of M) edge</span>
        {predicted && <span>Prediction disagreements: {graph.disagreements}</span>}
      </div>
    </div>
  );
}
export function Topology(props: {
  nodes: NodeInfo[];
  failed: string[];
  predicted?: string[];
  directFailed?: string[];
  selected?: string;
  onSelect?: (id: string) => void;
  before?: string[];
}) {
  return (
    <ReactFlowProvider>
      <GraphCore {...props} />
    </ReactFlowProvider>
  );
}
