import React, { useMemo, useCallback, useRef, useEffect, useState } from 'react';
import { cn } from '../utils/cn';
import { resolveAccessState, accessStyles, type AccessControlledProps } from '../internal/access-controller';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Node type identifiers matching ProcessFlow's BPMN-style taxonomy. */
export type FlowNodeType =
  | 'start'
  | 'end'
  | 'task'
  | 'decision'
  | 'subprocess'
  | 'timer'
  | 'message'
  | 'parallel-gateway';

/** A positioned node inside the flow builder canvas. */
export interface FlowNode {
  /** Unique identifier */
  id: string;
  /** BPMN-style node type controlling the rendered shape */
  type: FlowNodeType;
  /** Human-readable label displayed inside the node */
  label: string;
  /** Horizontal position (px) on the SVG canvas */
  x: number;
  /** Vertical position (px) on the SVG canvas */
  y: number;
  /** Override width (defaults to NODE_W) */
  width?: number;
  /** Override height (defaults to NODE_H) */
  height?: number;
  /** Arbitrary key-value metadata attached to the node */
  metadata?: Record<string, unknown>;
}

/** A directed edge connecting two nodes. */
export interface FlowEdge {
  /** Unique identifier */
  id: string;
  /** Source node id */
  from: string;
  /** Target node id */
  to: string;
  /** Optional label rendered at the edge midpoint */
  label?: string;
  /** Optional condition expression (for decision branches) */
  condition?: string;
}

/**
 * Props for the FlowBuilder interactive workflow designer.
 *
 * @example
 * ```tsx
 * <FlowBuilder
 *   nodes={[{ id: '1', type: 'start', label: 'Begin', x: 100, y: 100 }]}
 *   edges={[]}
 *   onNodesChange={setNodes}
 *   onEdgesChange={setEdges}
 *   showToolbar
 *   showGrid
 *   snapToGrid
 * />
 * ```
 *
 * @since 0.42.0
 */
export interface FlowBuilderProps extends AccessControlledProps {
  /** Flow nodes with positions */
  nodes: FlowNode[];
  /** Directed edges connecting nodes */
  edges: FlowEdge[];
  /** Called when the nodes array changes (drag, add, delete, property edit) */
  onNodesChange?: (nodes: FlowNode[]) => void;
  /** Called when the edges array changes */
  onEdgesChange?: (edges: FlowEdge[]) => void;
  /** Called when a single node is added */
  onNodeAdd?: (node: FlowNode) => void;
  /** Called when a node is deleted */
  onNodeDelete?: (nodeId: string) => void;
  /** Called when a single edge is added */
  onEdgeAdd?: (edge: FlowEdge) => void;
  /** Called when an edge is deleted */
  onEdgeDelete?: (edgeId: string) => void;
  /** Called when node selection changes */
  onNodeSelect?: (node: FlowNode | null) => void;
  /** Prevents all editing interactions */
  readOnly?: boolean;
  /** Show the minimap overview in bottom-right */
  showMinimap?: boolean;
  /** Show the top toolbar with node-type buttons and actions */
  showToolbar?: boolean;
  /** Show the dotted background grid */
  showGrid?: boolean;
  /** Snap node positions to the grid */
  snapToGrid?: boolean;
  /** Grid cell size in pixels */
  gridSize?: number;
  /** Canvas height (number = px, string = CSS value) */
  height?: number | string;
  /** Additional CSS class names */
  className?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const NODE_W = 120;
const NODE_H = 60;
const CIRCLE_R = 22;
const PORT_R = 6;
const MIN_ZOOM = 0.2;
const MAX_ZOOM = 3;
const DEFAULT_GRID = 20;

// ---------------------------------------------------------------------------
// Node types palette
// ---------------------------------------------------------------------------

const NODE_TYPE_LIST: { type: FlowNodeType; label: string }[] = [
  { type: 'start', label: 'Start' },
  { type: 'end', label: 'End' },
  { type: 'task', label: 'Task' },
  { type: 'decision', label: 'Decision' },
  { type: 'subprocess', label: 'Subprocess' },
  { type: 'timer', label: 'Timer' },
  { type: 'message', label: 'Message' },
  { type: 'parallel-gateway', label: 'Gateway' },
];

// ---------------------------------------------------------------------------
// Utility: unique id
// ---------------------------------------------------------------------------

let _idCounter = 0;
function uid(): string {
  _idCounter += 1;
  return `fb-${Date.now()}-${_idCounter}`;
}

// ---------------------------------------------------------------------------
// Snap helper
// ---------------------------------------------------------------------------

function snap(value: number, grid: number, enabled: boolean): number {
  if (!enabled) return value;
  return Math.round(value / grid) * grid;
}

// ---------------------------------------------------------------------------
// Node dimensions helper
// ---------------------------------------------------------------------------

function getNodeWidth(node: FlowNode): number {
  if (node.type === 'start' || node.type === 'end' || node.type === 'timer') return CIRCLE_R * 2;
  if (node.type === 'message') return NODE_W * 0.7;
  if (node.type === 'decision' || node.type === 'parallel-gateway') return 60;
  return node.width ?? NODE_W;
}

function getNodeHeight(node: FlowNode): number {
  if (node.type === 'start' || node.type === 'end' || node.type === 'timer') return CIRCLE_R * 2;
  if (node.type === 'message') return NODE_H * 0.55;
  if (node.type === 'decision' || node.type === 'parallel-gateway') return 60;
  return node.height ?? NODE_H;
}

// ---------------------------------------------------------------------------
// History entry
// ---------------------------------------------------------------------------

interface HistoryEntry {
  nodes: FlowNode[];
  edges: FlowEdge[];
}

// ---------------------------------------------------------------------------
// Node shape renderer (reuses ProcessFlow visual language)
// ---------------------------------------------------------------------------

function renderBuilderNodeShape(
  type: FlowNodeType,
  x: number,
  y: number,
  selected: boolean,
): React.ReactNode {
  const stroke = selected ? 'var(--action-primary)' : 'var(--border-strong)';
  const sw = selected ? 3 : 2;

  switch (type) {
    case 'start':
      return (
        <circle
          cx={x}
          cy={y}
          r={CIRCLE_R}
          fill="var(--state-success-text)"
          fillOpacity={0.2}
          stroke={selected ? 'var(--action-primary)' : 'var(--state-success-text)'}
          strokeWidth={sw}
        />
      );
    case 'end':
      return (
        <g>
          <circle
            cx={x}
            cy={y}
            r={CIRCLE_R}
            fill="var(--state-error-text)"
            fillOpacity={0.2}
            stroke={selected ? 'var(--action-primary)' : 'var(--state-error-text)'}
            strokeWidth={4}
          />
          <circle cx={x} cy={y} r={CIRCLE_R - 6} fill="var(--state-error-text)" fillOpacity={0.4} stroke="none" />
        </g>
      );
    case 'task':
      return (
        <rect
          x={x - NODE_W / 2}
          y={y - NODE_H / 2}
          width={NODE_W}
          height={NODE_H}
          rx={8}
          fill="var(--text-disabled)"
          fillOpacity={0.2}
          stroke={stroke}
          strokeWidth={sw}
        />
      );
    case 'decision': {
      const half = 30;
      const pts = `${x},${y - half} ${x + half},${y} ${x},${y + half} ${x - half},${y}`;
      return (
        <polygon
          points={pts}
          fill="var(--state-warning-text)"
          fillOpacity={0.2}
          stroke={selected ? 'var(--action-primary)' : 'var(--state-warning-text)'}
          strokeWidth={sw}
        />
      );
    }
    case 'subprocess':
      return (
        <g>
          <rect
            x={x - NODE_W / 2}
            y={y - NODE_H / 2}
            width={NODE_W}
            height={NODE_H}
            rx={4}
            fill="var(--text-disabled)"
            fillOpacity={0.2}
            stroke={stroke}
            strokeWidth={sw}
          />
          <rect
            x={x - NODE_W / 2 + 4}
            y={y - NODE_H / 2 + 4}
            width={NODE_W - 8}
            height={NODE_H - 8}
            rx={2}
            fill="none"
            stroke={stroke}
            strokeWidth={1}
          />
        </g>
      );
    case 'timer':
      return (
        <g>
          <circle
            cx={x}
            cy={y}
            r={CIRCLE_R}
            fill="var(--text-disabled)"
            fillOpacity={0.2}
            stroke={stroke}
            strokeWidth={sw}
            strokeDasharray="4 2"
          />
          <line x1={x} y1={y - 8} x2={x} y2={y} stroke={stroke} strokeWidth={1.5} />
          <line x1={x} y1={y} x2={x + 6} y2={y + 4} stroke={stroke} strokeWidth={1.5} />
        </g>
      );
    case 'message': {
      const w = NODE_W * 0.7;
      const h = NODE_H * 0.55;
      return (
        <g>
          <rect
            x={x - w / 2}
            y={y - h / 2}
            width={w}
            height={h}
            rx={2}
            fill="var(--text-disabled)"
            fillOpacity={0.2}
            stroke={stroke}
            strokeWidth={sw}
          />
          <polyline
            points={`${x - w / 2},${y - h / 2} ${x},${y + 2} ${x + w / 2},${y - h / 2}`}
            fill="none"
            stroke={stroke}
            strokeWidth={1.5}
          />
        </g>
      );
    }
    case 'parallel-gateway': {
      const half = 28;
      const pts = `${x},${y - half} ${x + half},${y} ${x},${y + half} ${x - half},${y}`;
      return (
        <g>
          <polygon
            points={pts}
            fill="var(--text-disabled)"
            fillOpacity={0.2}
            stroke={stroke}
            strokeWidth={sw}
          />
          <line x1={x - 10} y1={y} x2={x + 10} y2={y} stroke={stroke} strokeWidth={2} />
          <line x1={x} y1={y - 10} x2={x} y2={y + 10} stroke={stroke} strokeWidth={2} />
        </g>
      );
    }
    default:
      return (
        <rect
          x={x - NODE_W / 2}
          y={y - NODE_H / 2}
          width={NODE_W}
          height={NODE_H}
          rx={4}
          fill="var(--text-disabled)"
          fillOpacity={0.2}
          stroke={stroke}
          strokeWidth={sw}
        />
      );
  }
}

// ---------------------------------------------------------------------------
// Edge path builder (bezier)
// ---------------------------------------------------------------------------

function buildEdgePath(from: FlowNode, to: FlowNode): string {
  const fw = getNodeWidth(from);
  const th = getNodeWidth(to);
  const sx = from.x + fw / 2;
  const sy = from.y;
  const ex = to.x - th / 2;
  const ey = to.y;
  const mx = (sx + ex) / 2;
  return `M ${sx} ${sy} C ${mx} ${sy}, ${mx} ${ey}, ${ex} ${ey}`;
}

// ---------------------------------------------------------------------------
// FlowBuilder component
// ---------------------------------------------------------------------------

/**
 * Interactive no-code visual workflow designer built on top of ProcessFlow's
 * node shapes and edge routing. Provides a full SVG canvas with pan/zoom,
 * drag-to-connect edges, an undo/redo history stack, and a properties panel.
 *
 * @example
 * ```tsx
 * const [nodes, setNodes] = useState<FlowNode[]>([
 *   { id: '1', type: 'start', label: 'Begin', x: 100, y: 200 },
 *   { id: '2', type: 'task', label: 'Review', x: 300, y: 200 },
 *   { id: '3', type: 'end', label: 'Done', x: 500, y: 200 },
 * ]);
 * const [edges, setEdges] = useState<FlowEdge[]>([
 *   { id: 'e1', from: '1', to: '2' },
 *   { id: 'e2', from: '2', to: '3' },
 * ]);
 *
 * <FlowBuilder
 *   nodes={nodes}
 *   edges={edges}
 *   onNodesChange={setNodes}
 *   onEdgesChange={setEdges}
 *   showToolbar
 *   showGrid
 *   snapToGrid
 * />
 * ```
 *
 * @since 0.42.0
 */
export function FlowBuilder({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onNodeAdd,
  onNodeDelete,
  onEdgeAdd,
  onEdgeDelete,
  onNodeSelect,
  readOnly = false,
  showMinimap = false,
  showToolbar = true,
  showGrid = true,
  snapToGrid = false,
  gridSize = DEFAULT_GRID,
  height = 600,
  access,
  accessReason,
  className,
}: FlowBuilderProps) {
  const { state, isHidden } = resolveAccessState(access);
  const isInteractive = state === 'full' && !readOnly;

  // ---- Canvas state ----
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [isPanning, setIsPanning] = useState(false);
  const panStart = useRef({ x: 0, y: 0, panX: 0, panY: 0 });

  // ---- Selection state ----
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);

  // ---- Drag state ----
  const [draggingNodeId, setDraggingNodeId] = useState<string | null>(null);
  const dragStart = useRef({ x: 0, y: 0, nodeX: 0, nodeY: 0 });

  // ---- Edge drawing state ----
  const [connectingFrom, setConnectingFrom] = useState<string | null>(null);
  const [connectMouse, setConnectMouse] = useState({ x: 0, y: 0 });

  // ---- History (undo/redo) ----
  const [history, setHistory] = useState<HistoryEntry[]>([{ nodes, edges }]);
  const [historyIndex, setHistoryIndex] = useState(0);

  // Push new state to history
  const pushHistory = useCallback(
    (newNodes: FlowNode[], newEdges: FlowEdge[]) => {
      setHistory((prev) => {
        const trimmed = prev.slice(0, historyIndex + 1);
        return [...trimmed, { nodes: newNodes, edges: newEdges }];
      });
      setHistoryIndex((prev) => prev + 1);
    },
    [historyIndex],
  );

  // ---- Derived: selected node object ----
  const selectedNode = useMemo(() => nodes.find((n) => n.id === selectedNodeId) ?? null, [nodes, selectedNodeId]);

  // ---- Notify selection ----
  useEffect(() => {
    onNodeSelect?.(selectedNode);
  }, [selectedNode, onNodeSelect]);

  // ---- SVG mouse → canvas coords ----
  const toCanvas = useCallback(
    (clientX: number, clientY: number) => {
      const rect = svgRef.current?.getBoundingClientRect();
      if (!rect) return { x: 0, y: 0 };
      return {
        x: (clientX - rect.left - pan.x) / zoom,
        y: (clientY - rect.top - pan.y) / zoom,
      };
    },
    [pan, zoom],
  );

  // ================================================================
  // Canvas pan handlers
  // ================================================================

  const handleCanvasMouseDown = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      // Only pan on background click (not on nodes/edges)
      if ((e.target as SVGElement).closest('[data-flow-node]') || (e.target as SVGElement).closest('[data-flow-port]')) {
        return;
      }
      // Deselect
      if (selectedNodeId) {
        setSelectedNodeId(null);
      }
      if (selectedEdgeId) {
        setSelectedEdgeId(null);
      }
      setIsPanning(true);
      panStart.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y };
    },
    [pan, selectedNodeId, selectedEdgeId],
  );

  const handleCanvasMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      // Edge connection preview
      if (connectingFrom) {
        const pt = toCanvas(e.clientX, e.clientY);
        setConnectMouse(pt);
        return;
      }

      // Panning
      if (isPanning) {
        const dx = e.clientX - panStart.current.x;
        const dy = e.clientY - panStart.current.y;
        setPan({ x: panStart.current.panX + dx, y: panStart.current.panY + dy });
        return;
      }

      // Dragging a node
      if (draggingNodeId && isInteractive) {
        const dx = (e.clientX - dragStart.current.x) / zoom;
        const dy = (e.clientY - dragStart.current.y) / zoom;
        const newX = snap(dragStart.current.nodeX + dx, gridSize, snapToGrid);
        const newY = snap(dragStart.current.nodeY + dy, gridSize, snapToGrid);
        const updated = nodes.map((n) => (n.id === draggingNodeId ? { ...n, x: newX, y: newY } : n));
        onNodesChange?.(updated);
      }
    },
    [isPanning, draggingNodeId, connectingFrom, isInteractive, zoom, gridSize, snapToGrid, nodes, onNodesChange, toCanvas],
  );

  const handleCanvasMouseUp = useCallback(
    (_e: React.MouseEvent<SVGSVGElement>) => {
      if (draggingNodeId) {
        pushHistory(nodes, edges);
        setDraggingNodeId(null);
      }
      if (connectingFrom) {
        setConnectingFrom(null);
      }
      setIsPanning(false);
    },
    [draggingNodeId, connectingFrom, nodes, edges, pushHistory],
  );

  // ================================================================
  // Zoom handler (wheel)
  // ================================================================

  const handleWheel = useCallback(
    (e: React.WheelEvent<SVGSVGElement>) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      setZoom((z) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z * delta)));
    },
    [],
  );

  // ================================================================
  // Node interaction
  // ================================================================

  const handleNodeMouseDown = useCallback(
    (e: React.MouseEvent, nodeId: string) => {
      e.stopPropagation();
      if (!isInteractive) return;
      setSelectedNodeId(nodeId);
      setSelectedEdgeId(null);
      setDraggingNodeId(nodeId);
      const node = nodes.find((n) => n.id === nodeId);
      if (node) {
        dragStart.current = { x: e.clientX, y: e.clientY, nodeX: node.x, nodeY: node.y };
      }
    },
    [isInteractive, nodes],
  );

  const handleNodeClick = useCallback(
    (e: React.MouseEvent, nodeId: string) => {
      e.stopPropagation();
      setSelectedNodeId(nodeId);
      setSelectedEdgeId(null);
    },
    [],
  );

  // ================================================================
  // Port interaction (edge drawing)
  // ================================================================

  const handleOutputPortMouseDown = useCallback(
    (e: React.MouseEvent, nodeId: string) => {
      e.stopPropagation();
      if (!isInteractive) return;
      setConnectingFrom(nodeId);
      const pt = toCanvas(e.clientX, e.clientY);
      setConnectMouse(pt);
    },
    [isInteractive, toCanvas],
  );

  const handleInputPortMouseUp = useCallback(
    (e: React.MouseEvent, nodeId: string) => {
      e.stopPropagation();
      if (!connectingFrom || connectingFrom === nodeId) {
        setConnectingFrom(null);
        return;
      }
      // Check for duplicate edge
      const exists = edges.some((ed) => ed.from === connectingFrom && ed.to === nodeId);
      if (!exists) {
        const newEdge: FlowEdge = { id: uid(), from: connectingFrom, to: nodeId };
        const newEdges = [...edges, newEdge];
        onEdgesChange?.(newEdges);
        onEdgeAdd?.(newEdge);
        pushHistory(nodes, newEdges);
      }
      setConnectingFrom(null);
    },
    [connectingFrom, edges, nodes, onEdgesChange, onEdgeAdd, pushHistory],
  );

  // ================================================================
  // Edge selection
  // ================================================================

  const handleEdgeClick = useCallback(
    (e: React.MouseEvent, edgeId: string) => {
      e.stopPropagation();
      setSelectedEdgeId(edgeId);
      setSelectedNodeId(null);
    },
    [],
  );

  // ================================================================
  // Delete selected
  // ================================================================

  const deleteSelected = useCallback(() => {
    if (!isInteractive) return;
    if (selectedNodeId) {
      const newNodes = nodes.filter((n) => n.id !== selectedNodeId);
      const newEdges = edges.filter((ed) => ed.from !== selectedNodeId && ed.to !== selectedNodeId);
      onNodesChange?.(newNodes);
      onEdgesChange?.(newEdges);
      onNodeDelete?.(selectedNodeId);
      pushHistory(newNodes, newEdges);
      setSelectedNodeId(null);
    } else if (selectedEdgeId) {
      const newEdges = edges.filter((ed) => ed.id !== selectedEdgeId);
      onEdgesChange?.(newEdges);
      onEdgeDelete?.(selectedEdgeId);
      pushHistory(nodes, newEdges);
      setSelectedEdgeId(null);
    }
  }, [isInteractive, selectedNodeId, selectedEdgeId, nodes, edges, onNodesChange, onEdgesChange, onNodeDelete, onEdgeDelete, pushHistory]);

  // ================================================================
  // Undo / Redo
  // ================================================================

  const undo = useCallback(() => {
    if (historyIndex <= 0) return;
    const newIndex = historyIndex - 1;
    const entry = history[newIndex];
    if (entry) {
      setHistoryIndex(newIndex);
      onNodesChange?.(entry.nodes);
      onEdgesChange?.(entry.edges);
    }
  }, [historyIndex, history, onNodesChange, onEdgesChange]);

  const redo = useCallback(() => {
    if (historyIndex >= history.length - 1) return;
    const newIndex = historyIndex + 1;
    const entry = history[newIndex];
    if (entry) {
      setHistoryIndex(newIndex);
      onNodesChange?.(entry.nodes);
      onEdgesChange?.(entry.edges);
    }
  }, [historyIndex, history, onNodesChange, onEdgesChange]);

  // ================================================================
  // Add node from toolbar
  // ================================================================

  const addNode = useCallback(
    (type: FlowNodeType) => {
      if (!isInteractive) return;
      const rect = svgRef.current?.getBoundingClientRect();
      const cx = rect ? rect.width / 2 : 300;
      const cy = rect ? rect.height / 2 : 200;
      const canvasPos = {
        x: snap((cx - pan.x) / zoom, gridSize, snapToGrid),
        y: snap((cy - pan.y) / zoom, gridSize, snapToGrid),
      };
      const node: FlowNode = {
        id: uid(),
        type,
        label: type.charAt(0).toUpperCase() + type.slice(1),
        x: canvasPos.x,
        y: canvasPos.y,
      };
      const newNodes = [...nodes, node];
      onNodesChange?.(newNodes);
      onNodeAdd?.(node);
      pushHistory(newNodes, edges);
      setSelectedNodeId(node.id);
    },
    [isInteractive, nodes, edges, pan, zoom, gridSize, snapToGrid, onNodesChange, onNodeAdd, pushHistory],
  );

  // ================================================================
  // Zoom controls
  // ================================================================

  const zoomIn = useCallback(() => setZoom((z) => Math.min(MAX_ZOOM, z * 1.2)), []);
  const zoomOut = useCallback(() => setZoom((z) => Math.max(MIN_ZOOM, z / 1.2)), []);
  const zoomFit = useCallback(() => {
    if (nodes.length === 0) return;
    const xs = nodes.map((n) => n.x);
    const ys = nodes.map((n) => n.y);
    const minX = Math.min(...xs) - 100;
    const maxX = Math.max(...xs) + 100;
    const minY = Math.min(...ys) - 100;
    const maxY = Math.max(...ys) + 100;
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const scaleX = rect.width / (maxX - minX);
    const scaleY = rect.height / (maxY - minY);
    const newZoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Math.min(scaleX, scaleY)));
    setZoom(newZoom);
    setPan({
      x: rect.width / 2 - ((minX + maxX) / 2) * newZoom,
      y: rect.height / 2 - ((minY + maxY) / 2) * newZoom,
    });
  }, [nodes]);

  // ================================================================
  // Keyboard shortcuts
  // ================================================================

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!isInteractive) return;
      if (e.key === 'Delete' || e.key === 'Backspace') {
        // Don't intercept if user is typing in an input
        if ((e.target as HTMLElement).tagName === 'INPUT' || (e.target as HTMLElement).tagName === 'TEXTAREA') return;
        deleteSelected();
      }
      if (e.key === 'Escape') {
        setSelectedNodeId(null);
        setSelectedEdgeId(null);
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        e.preventDefault();
        undo();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'y') {
        e.preventDefault();
        redo();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isInteractive, deleteSelected, undo, redo]);

  // ================================================================
  // Node property editing
  // ================================================================

  const updateNodeLabel = useCallback(
    (label: string) => {
      if (!selectedNodeId || !isInteractive) return;
      const updated = nodes.map((n) => (n.id === selectedNodeId ? { ...n, label } : n));
      onNodesChange?.(updated);
    },
    [selectedNodeId, isInteractive, nodes, onNodesChange],
  );

  const updateNodeType = useCallback(
    (type: FlowNodeType) => {
      if (!selectedNodeId || !isInteractive) return;
      const updated = nodes.map((n) => (n.id === selectedNodeId ? { ...n, type } : n));
      onNodesChange?.(updated);
      pushHistory(updated, edges);
    },
    [selectedNodeId, isInteractive, nodes, edges, onNodesChange, pushHistory],
  );

  const updateNodeMetadata = useCallback(
    (key: string, value: string) => {
      if (!selectedNodeId || !isInteractive) return;
      const updated = nodes.map((n) => {
        if (n.id !== selectedNodeId) return n;
        const metadata = { ...(n.metadata ?? {}), [key]: value };
        return { ...n, metadata };
      });
      onNodesChange?.(updated);
    },
    [selectedNodeId, isInteractive, nodes, onNodesChange],
  );

  // ================================================================
  // Minimap
  // ================================================================

  const minimapContent = useMemo(() => {
    if (!showMinimap || nodes.length === 0) return null;
    const xs = nodes.map((n) => n.x);
    const ys = nodes.map((n) => n.y);
    const minX = Math.min(...xs) - 50;
    const maxX = Math.max(...xs) + 50;
    const minY = Math.min(...ys) - 50;
    const maxY = Math.max(...ys) + 50;
    const w = maxX - minX || 200;
    const h = maxY - minY || 120;
    return (
      <svg
        className="absolute bottom-2 right-2 rounded border border-border-default bg-[var(--surface-default)]"
        width={150}
        height={100}
        viewBox={`${minX} ${minY} ${w} ${h}`}
        data-testid="flow-minimap"
      >
        {edges.map((ed) => {
          const from = nodes.find((n) => n.id === ed.from);
          const to = nodes.find((n) => n.id === ed.to);
          if (!from || !to) return null;
          return (
            <line
              key={ed.id}
              x1={from.x}
              y1={from.y}
              x2={to.x}
              y2={to.y}
              stroke="var(--border-strong)"
              strokeWidth={2}
            />
          );
        })}
        {nodes.map((n) => (
          <circle
            key={n.id}
            cx={n.x}
            cy={n.y}
            r={6}
            fill={n.id === selectedNodeId ? 'var(--action-primary)' : 'var(--text-secondary)'}
          />
        ))}
      </svg>
    );
  }, [showMinimap, nodes, edges, selectedNodeId]);

  // ================================================================
  // Render
  // ================================================================

  if (isHidden) return null;

  const canvasStyle: React.CSSProperties = {
    height: typeof height === 'number' ? `${height}px` : height,
  };

  return (
    <div
      ref={containerRef}
      className={cn(
        'relative flex overflow-hidden rounded-lg border border-border-default bg-[var(--surface-primary)]',
        accessStyles(state),
        className,
      )}
      style={canvasStyle}
      data-testid="flow-builder"
      data-access-state={state}
      role="application"
      aria-label="Flow builder canvas"
      title={accessReason}
    >
      {/* ---- Toolbar ---- */}
      {showToolbar && (
        <div
          className="absolute top-0 left-0 right-0 z-10 flex flex-wrap items-center gap-1 border-b border-border-default bg-[var(--surface-default)] px-2 py-1"
          data-testid="flow-toolbar"
          role="toolbar"
          aria-label="Flow builder toolbar"
        >
          {NODE_TYPE_LIST.map((nt) => (
            <button
              key={nt.type}
              type="button"
              className="rounded-md border border-border-default bg-[var(--surface-primary)] px-2 py-1 text-xs text-[var(--text-primary)] hover:bg-[var(--surface-muted)] disabled:opacity-50"
              onClick={() => addNode(nt.type)}
              disabled={!isInteractive}
              data-testid={`add-${nt.type}`}
              aria-label={`Add ${nt.label} node`}
            >
              {nt.label}
            </button>
          ))}

          <span className="mx-1 h-4 w-px bg-border-default" />

          <button
            type="button"
            className="rounded-md border border-border-default px-2 py-1 text-xs text-[var(--text-primary)] hover:bg-[var(--surface-muted)]"
            onClick={zoomIn}
            aria-label="Zoom in"
            data-testid="zoom-in"
          >
            +
          </button>
          <button
            type="button"
            className="rounded-md border border-border-default px-2 py-1 text-xs text-[var(--text-primary)] hover:bg-[var(--surface-muted)]"
            onClick={zoomOut}
            aria-label="Zoom out"
            data-testid="zoom-out"
          >
            -
          </button>
          <button
            type="button"
            className="rounded-md border border-border-default px-2 py-1 text-xs text-[var(--text-primary)] hover:bg-[var(--surface-muted)]"
            onClick={zoomFit}
            aria-label="Zoom to fit"
            data-testid="zoom-fit"
          >
            Fit
          </button>

          <span className="mx-1 h-4 w-px bg-border-default" />

          <button
            type="button"
            className="rounded-md border border-border-default px-2 py-1 text-xs text-[var(--text-primary)] hover:bg-[var(--surface-muted)] disabled:opacity-50"
            onClick={undo}
            disabled={historyIndex <= 0}
            aria-label="Undo"
            data-testid="undo"
          >
            Undo
          </button>
          <button
            type="button"
            className="rounded-md border border-border-default px-2 py-1 text-xs text-[var(--text-primary)] hover:bg-[var(--surface-muted)] disabled:opacity-50"
            onClick={redo}
            disabled={historyIndex >= history.length - 1}
            aria-label="Redo"
            data-testid="redo"
          >
            Redo
          </button>

          <button
            type="button"
            className="rounded-md border border-border-default px-2 py-1 text-xs text-[var(--state-error-text)] hover:bg-[var(--surface-muted)] disabled:opacity-50"
            onClick={deleteSelected}
            disabled={!isInteractive || (!selectedNodeId && !selectedEdgeId)}
            aria-label="Delete selected"
            data-testid="delete-selected"
          >
            Delete
          </button>
        </div>
      )}

      {/* ---- SVG Canvas ---- */}
      <svg
        ref={svgRef}
        className="h-full w-full cursor-grab active:cursor-grabbing"
        style={{ marginTop: showToolbar ? 36 : 0 }}
        onMouseDown={handleCanvasMouseDown}
        onMouseMove={handleCanvasMouseMove}
        onMouseUp={handleCanvasMouseUp}
        onMouseLeave={handleCanvasMouseUp}
        onWheel={handleWheel}
        data-testid="flow-canvas"
        aria-label="Flow builder SVG canvas"
      >
        <defs>
          <marker
            id="fb-arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="6"
            markerHeight="6"
            orient="auto-start-reverse"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--border-strong)" />
          </marker>
          {/* Grid pattern */}
          {showGrid && (
            <pattern id="fb-grid" width={gridSize} height={gridSize} patternUnits="userSpaceOnUse">
              <circle cx={1} cy={1} r={0.8} fill="var(--text-disabled)" fillOpacity={0.3} />
            </pattern>
          )}
        </defs>

        {/* Transform group for pan & zoom */}
        <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
          {/* Grid background */}
          {showGrid && (
            <rect
              x={-5000}
              y={-5000}
              width={10000}
              height={10000}
              fill="url(#fb-grid)"
              className="pointer-events-none"
            />
          )}

          {/* Edges */}
          {edges.map((ed) => {
            const from = nodes.find((n) => n.id === ed.from);
            const to = nodes.find((n) => n.id === ed.to);
            if (!from || !to) return null;
            const d = buildEdgePath(from, to);
            const isSelected = ed.id === selectedEdgeId;
            const mx = (from.x + to.x) / 2;
            const my = (from.y + to.y) / 2;
            return (
              <g key={ed.id}>
                {/* Invisible thick click target */}
                <path
                  d={d}
                  fill="none"
                  stroke="transparent"
                  strokeWidth={12}
                  role="button"
                  tabIndex={0}
                  style={{ cursor: 'pointer' }}
                  onClick={(e) => handleEdgeClick(e, ed.id)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleEdgeClick(e as unknown as React.MouseEvent, ed.id); } }}
                />
                <path
                  d={d}
                  fill="none"
                  stroke={isSelected ? 'var(--action-primary)' : 'var(--border-strong)'}
                  strokeWidth={isSelected ? 2.5 : 1.5}
                  markerEnd="url(#fb-arrow)"
                  className="pointer-events-none"
                  data-flow-edge={ed.id}
                />
                {ed.label && (
                  <text
                    x={mx}
                    y={my - 6}
                    textAnchor="middle"
                    fontSize={10}
                    fill="var(--text-secondary)"
                    className="pointer-events-none"
                  >
                    {ed.label}
                  </text>
                )}
              </g>
            );
          })}

          {/* Temporary edge while connecting */}
          {connectingFrom && (() => {
            const fromNode = nodes.find((n) => n.id === connectingFrom);
            if (!fromNode) return null;
            const fw = getNodeWidth(fromNode);
            return (
              <line
                x1={fromNode.x + fw / 2}
                y1={fromNode.y}
                x2={connectMouse.x}
                y2={connectMouse.y}
                stroke="var(--action-primary)"
                strokeWidth={2}
                strokeDasharray="6 3"
                className="pointer-events-none"
                data-testid="connecting-line"
              />
            );
          })()}

          {/* Nodes */}
          {nodes.map((node) => {
            const isSelected = node.id === selectedNodeId;
            const nw = getNodeWidth(node);
            const nh = getNodeHeight(node);

            return (
              <g
                key={node.id}
                data-flow-node={node.id}
                data-testid={`node-${node.id}`}
                className="cursor-pointer"
                onMouseDown={(e) => handleNodeMouseDown(e, node.id)}
                onClick={(e) => handleNodeClick(e, node.id)}
                role="button"
                tabIndex={0}
                aria-label={`${node.label} (${node.type})`}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    setSelectedNodeId(node.id);
                  }
                }}
              >
                {renderBuilderNodeShape(node.type, node.x, node.y, isSelected)}

                {/* Label */}
                <text
                  x={node.x}
                  y={node.y + 4}
                  textAnchor="middle"
                  fontSize={11}
                  fill="var(--text-primary)"
                  className="pointer-events-none select-none"
                >
                  {node.label.length > 14 ? node.label.slice(0, 13) + '\u2026' : node.label}
                </text>

                {/* Output port (right side) */}
                {isInteractive && (
                  <circle
                    cx={node.x + nw / 2}
                    cy={node.y}
                    r={PORT_R}
                    fill="var(--surface-default)"
                    stroke="var(--action-primary)"
                    strokeWidth={1.5}
                    className="cursor-crosshair"
                    data-flow-port="output"
                    data-testid={`port-output-${node.id}`}
                    onMouseDown={(e) => handleOutputPortMouseDown(e, node.id)}
                  />
                )}

                {/* Input port (left side) */}
                {isInteractive && (
                  <circle
                    cx={node.x - nw / 2}
                    cy={node.y}
                    r={PORT_R}
                    fill="var(--surface-default)"
                    stroke="var(--text-secondary)"
                    strokeWidth={1.5}
                    className="cursor-crosshair"
                    data-flow-port="input"
                    data-testid={`port-input-${node.id}`}
                    onMouseUp={(e) => handleInputPortMouseUp(e, node.id)}
                  />
                )}

                {/* Delete button on selected */}
                {isSelected && isInteractive && (
                  <g
                    role="button"
                    tabIndex={0}
                    className="cursor-pointer"
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteSelected();
                    }}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); deleteSelected(); } }}
                    data-testid={`delete-node-${node.id}`}
                  >
                    <circle
                      cx={node.x + nw / 2 - 2}
                      cy={node.y - nh / 2 + 2}
                      r={8}
                      fill="var(--state-error-text)"
                      stroke="var(--surface-default)"
                      strokeWidth={1.5}
                    />
                    <text
                      x={node.x + nw / 2 - 2}
                      y={node.y - nh / 2 + 6}
                      textAnchor="middle"
                      fontSize={10}
                      fill="var(--text-inverse)"
                      fontWeight="bold"
                      className="pointer-events-none select-none"
                    >
                      ×
                    </text>
                  </g>
                )}
              </g>
            );
          })}
        </g>
      </svg>

      {/* ---- Minimap ---- */}
      {minimapContent}

      {/* ---- Properties Panel (right sidebar) ---- */}
      {selectedNode && isInteractive && (
        <div
          className="absolute top-0 right-0 bottom-0 z-20 flex w-64 flex-col gap-3 overflow-y-auto border-l border-border-default bg-[var(--surface-default)] p-3"
          style={{ marginTop: showToolbar ? 36 : 0 }}
          data-testid="properties-panel"
        >
          <h3 className="text-sm font-semibold text-[var(--text-primary)]">Node Properties</h3>

          {/* Label */}
          <label className="flex flex-col gap-1 text-xs text-[var(--text-secondary)]">
            Label
            <input
              type="text"
              value={selectedNode.label}
              onChange={(e) => updateNodeLabel(e.target.value)}
              onBlur={() => pushHistory(nodes, edges)}
              className="rounded border border-border-default bg-[var(--surface-primary)] px-2 py-1 text-sm text-[var(--text-primary)]"
              data-testid="node-label-input"
            />
          </label>

          {/* Type */}
          <label className="flex flex-col gap-1 text-xs text-[var(--text-secondary)]">
            Type
            <select
              value={selectedNode.type}
              onChange={(e) => updateNodeType(e.target.value as FlowNodeType)}
              className="rounded border border-border-default bg-[var(--surface-primary)] px-2 py-1 text-sm text-[var(--text-primary)]"
              data-testid="node-type-select"
            >
              {NODE_TYPE_LIST.map((nt) => (
                <option key={nt.type} value={nt.type}>
                  {nt.label}
                </option>
              ))}
            </select>
          </label>

          {/* Metadata */}
          <div className="flex flex-col gap-1">
            <span className="text-xs text-[var(--text-secondary)]">Metadata</span>
            {Object.entries(selectedNode.metadata ?? {}).map(([key, val]) => (
              <div key={key} className="flex gap-1">
                <input
                  type="text"
                  value={key}
                  readOnly
                  className="w-1/2 rounded border border-border-default bg-[var(--surface-muted)] px-1 py-0.5 text-xs text-[var(--text-primary)]"
                />
                <input
                  type="text"
                  value={String(val ?? '')}
                  onChange={(e) => updateNodeMetadata(key, e.target.value)}
                  className="w-1/2 rounded border border-border-default bg-[var(--surface-primary)] px-1 py-0.5 text-xs text-[var(--text-primary)]"
                  data-testid={`meta-${key}`}
                />
              </div>
            ))}
            <button
              type="button"
              className="mt-1 rounded border border-border-default px-2 py-0.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--surface-muted)]"
              onClick={() => {
                const key = `key-${Object.keys(selectedNode.metadata ?? {}).length + 1}`;
                updateNodeMetadata(key, '');
              }}
              data-testid="add-metadata"
            >
              + Add field
            </button>
          </div>

          <div className="mt-auto pt-2 text-[10px] text-[var(--text-disabled)]">
            ID: {selectedNode.id}
          </div>
        </div>
      )}

      {/* ---- Empty state ---- */}
      {nodes.length === 0 && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center" data-testid="empty-state">
          <span className="text-sm text-[var(--text-disabled)]">
            {isInteractive ? 'Click a node type above to start building' : 'No workflow defined'}
          </span>
        </div>
      )}
    </div>
  );
}

FlowBuilder.displayName = 'FlowBuilder';
