import React, { useState, useMemo, _useCallback, useEffect, _useRef } from "react";
import {
  Activity,
  ChevronDown,
  ChevronRight,
  Timer,
  Zap,
  AlertTriangle,
  RotateCcw,
  TrendingUp,
} from "lucide-react";
import { Text } from "@mfe/design-system";

/* ------------------------------------------------------------------ */
/*  PerfProfilerPanel — Render performance metrics                      */
/*                                                                     */
/*  Features:                                                          */
/*  - Tracks render time per interaction                               */
/*  - Re-render count and average time                                 */
/*  - SVG Sparkline of last 20 renders                                 */
/*  - Warning badge for renders > 16ms (60fps threshold)               */
/*  - Unique feature — no competitor has this                          */
/* ------------------------------------------------------------------ */

export type PerfMetric = {
  id: number;
  phase: "mount" | "update";
  actualDuration: number;
  baseDuration: number;
  timestamp: number;
  propChange?: string;
};

/* ---- Ring buffer for metrics ---- */

const MAX_METRICS = 30;
let _metricsBuffer: PerfMetric[] = [];
let _metricsId = 0;
const _subscribers = new Set<() => void>();

export function recordPerfMetric(metric: Omit<PerfMetric, "id">) {
  const entry: PerfMetric = { ...metric, id: _metricsId++ };
  _metricsBuffer.push(entry);
  if (_metricsBuffer.length > MAX_METRICS) {
    _metricsBuffer = _metricsBuffer.slice(-MAX_METRICS);
  }
  _subscribers.forEach((fn) => fn());
}

export function subscribeToPerfMetrics(fn: () => void): () => void {
  _subscribers.add(fn);
  return () => { _subscribers.delete(fn); };
}

export function getPerfMetrics(): PerfMetric[] {
  return [..._metricsBuffer];
}

export function clearPerfMetrics(): void {
  _metricsBuffer = [];
  _metricsId = 0;
  _subscribers.forEach((fn) => fn());
}

/* ---- SVG Sparkline ---- */

const SvgSparkline: React.FC<{ data: number[]; width?: number; height?: number; threshold?: number }> = ({
  data,
  width = 200,
  height = 40,
  threshold = 16,
}) => {
  if (data.length < 2) return null;

  const max = Math.max(...data, threshold * 1.5);
  const min = 0;
  const range = max - min || 1;

  const points = data.map((val, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((val - min) / range) * height;
    return `${x},${y}`;
  }).join(" ");

  const thresholdY = height - ((threshold - min) / range) * height;

  return (
    <svg width={width} height={height} className="overflow-visible">
      {/* Threshold line */}
      <line
        x1={0} y1={thresholdY} x2={width} y2={thresholdY}
        stroke="var(--state-danger-text)" strokeWidth={1} strokeDasharray="4,4" opacity={0.5}
      />
      <text x={width + 4} y={thresholdY + 3} fontSize={8} fill="var(--state-danger-text)">16ms</text>

      {/* Data line */}
      <polyline
        points={points}
        fill="none"
        stroke="var(--action-primary)"
        strokeWidth={1.5}
        strokeLinejoin="round"
      />

      {/* Data dots */}
      {data.map((val, i) => {
        const x = (i / (data.length - 1)) * width;
        const y = height - ((val - min) / range) * height;
        return (
          <circle
            key={i}
            cx={x}
            cy={y}
            r={2}
            fill={val > threshold ? "var(--state-danger-text)" : "var(--action-primary)"}
          />
        );
      })}
    </svg>
  );
};

/* ---- Panel Component ---- */

type PerfProfilerPanelProps = {
  expanded: boolean;
  onToggle: () => void;
};

export const PerfProfilerPanel: React.FC<PerfProfilerPanelProps> = ({ expanded, onToggle }) => {
  const [, forceUpdate] = useState(0);

  useEffect(() => {
    return subscribeToPerfMetrics(() => forceUpdate((c) => c + 1));
  }, []);

  const metrics = getPerfMetrics();

  const stats = useMemo(() => {
    if (metrics.length === 0) return null;
    const durations = metrics.map((m) => m.actualDuration);
    const avg = durations.reduce((a, b) => a + b, 0) / durations.length;
    const maxDuration = Math.max(...durations);
    const minDuration = Math.min(...durations);
    const mountCount = metrics.filter((m) => m.phase === "mount").length;
    const updateCount = metrics.filter((m) => m.phase === "update").length;
    const slowRenders = metrics.filter((m) => m.actualDuration > 16).length;
    return { avg, maxDuration, minDuration, mountCount, updateCount, slowRenders, total: metrics.length };
  }, [metrics]);

  const sparklineData = useMemo(() => metrics.slice(-20).map((m) => m.actualDuration), [metrics]);

  return (
    <div className="border-t border-border-subtle">
      {/* Header */}
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between px-4 py-2.5 hover:bg-surface-muted/50 transition"
      >
        <div className="flex items-center gap-2">
          <Activity className="h-3.5 w-3.5 text-text-tertiary" />
          <Text as="span" className="text-xs font-semibold text-text-primary">Performance</Text>
          {stats && stats.slowRenders > 0 && (
            <span className="flex items-center gap-1 rounded-md bg-state-danger-bg px-1.5 py-0.5 text-[10px] font-semibold text-state-danger-text">
              <AlertTriangle className="h-2.5 w-2.5" /> {stats.slowRenders} slow
            </span>
          )}
          {stats && stats.slowRenders === 0 && (
            <span className="rounded-md bg-state-success-bg px-1.5 py-0.5 text-[10px] font-semibold text-state-success-text">
              Fast
            </span>
          )}
        </div>
        {expanded ? <ChevronDown className="h-3.5 w-3.5 text-text-tertiary" /> : <ChevronRight className="h-3.5 w-3.5 text-text-tertiary" />}
      </button>

      {expanded && (
        <div className="flex flex-col border-t border-border-subtle px-4 py-3 gap-3">
          {!stats ? (
            <div className="flex items-center gap-2 rounded-xl bg-surface-canvas p-3">
              <Timer className="h-4 w-4 text-text-tertiary" />
              <Text variant="secondary" className="text-xs">
                Interact with the component to collect performance data.
              </Text>
            </div>
          ) : (
            <>
              {/* Stats grid */}
              <div className="grid grid-cols-4 gap-2">
                <div className="rounded-xl bg-surface-canvas p-2.5 text-center">
                  <Text variant="secondary" className="text-[9px] font-semibold uppercase tracking-wider">Avg</Text>
                  <Text as="div" className="text-sm font-bold text-text-primary">{stats.avg.toFixed(1)}ms</Text>
                </div>
                <div className="rounded-xl bg-surface-canvas p-2.5 text-center">
                  <Text variant="secondary" className="text-[9px] font-semibold uppercase tracking-wider">Max</Text>
                  <Text as="div" className={`text-sm font-bold ${stats.maxDuration > 16 ? "text-state-danger-text" : "text-text-primary"}`}>
                    {stats.maxDuration.toFixed(1)}ms
                  </Text>
                </div>
                <div className="rounded-xl bg-surface-canvas p-2.5 text-center">
                  <Text variant="secondary" className="text-[9px] font-semibold uppercase tracking-wider">Renders</Text>
                  <Text as="div" className="text-sm font-bold text-text-primary">{stats.total}</Text>
                </div>
                <div className="rounded-xl bg-surface-canvas p-2.5 text-center">
                  <Text variant="secondary" className="text-[9px] font-semibold uppercase tracking-wider">Slow</Text>
                  <Text as="div" className={`text-sm font-bold ${stats.slowRenders > 0 ? "text-state-danger-text" : "text-state-success-text"}`}>
                    {stats.slowRenders}
                  </Text>
                </div>
              </div>

              {/* Sparkline */}
              {sparklineData.length >= 2 && (
                <div className="rounded-xl bg-surface-canvas p-3">
                  <div className="flex items-center justify-between mb-2">
                    <Text variant="secondary" className="text-[10px] font-semibold">
                      Render Timeline (last {sparklineData.length})
                    </Text>
                    <button
                      type="button"
                      onClick={clearPerfMetrics}
                      className="flex items-center gap-1 text-[10px] text-text-tertiary hover:text-text-primary transition"
                    >
                      <RotateCcw className="h-2.5 w-2.5" /> Clear
                    </button>
                  </div>
                  <SvgSparkline data={sparklineData} width={280} height={40} />
                </div>
              )}

              {/* Recent renders */}
              <div className="flex flex-col max-h-32 overflow-y-auto gap-1">
                {metrics.slice(-10).reverse().map((m) => (
                  <div key={m.id} className="flex items-center gap-2 rounded-lg px-2 py-1 text-[11px] hover:bg-surface-muted/50">
                    <span className={`h-1.5 w-1.5 rounded-full ${m.actualDuration > 16 ? "bg-state-danger-text" : "bg-state-success-text"}`} />
                    <span className="text-text-tertiary font-mono w-16">{m.phase}</span>
                    <span className={`font-mono font-medium ${m.actualDuration > 16 ? "text-state-danger-text" : "text-text-primary"}`}>
                      {m.actualDuration.toFixed(2)}ms
                    </span>
                    {m.propChange && (
                      <span className="text-text-tertiary truncate">{m.propChange}</span>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default PerfProfilerPanel;
