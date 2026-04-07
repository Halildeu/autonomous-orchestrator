/**
 * SunburstChart -- ECharts-powered hierarchical sunburst chart
 *
 * Renders a hierarchical ring visualization where each concentric ring
 * represents a level in the data tree. Supports configurable radius,
 * sorting, per-level styling, and descendant/ancestor highlighting.
 *
 * Uses the centralized useEChartsRenderer hook for lifecycle management.
 *
 * @migration AG Charts -> ECharts (P3)
 */
import React, { useMemo, useCallback } from "react";
import { cn } from "@mfe/design-system";
import { useEChartsRenderer } from "./renderers";
import { buildDesignLabEChartsTheme } from "./theme/DesignLabEChartsTheme";
import { formatCompact } from "./utils/formatters";
import type { EChartsOption } from "./renderers/echarts-imports";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface SunburstNode {
  /** Display name for this node. */
  name: string;
  /** Leaf value. For branches, ECharts aggregates children automatically. */
  value?: number;
  /** Child nodes forming the next ring outward. */
  children?: SunburstNode[];
  /** Optional per-node style overrides. */
  itemStyle?: { color?: string; [key: string]: unknown };
}

export interface SunburstLevelConfig {
  /** Inner radius for this level (e.g. "15%"). */
  r0?: string;
  /** Outer radius for this level (e.g. "35%"). */
  r1?: string;
  /** Item style overrides for this level. */
  itemStyle?: Record<string, unknown>;
  /** Label overrides for this level. */
  label?: Record<string, unknown>;
}

export type SunburstHighlightPolicy = "descendant" | "ancestor" | "self" | "none";

export interface SunburstChartProps {
  /** Hierarchical data tree (top-level children form the inner ring). */
  data: SunburstNode[];
  /** Visual size variant. @default "md" */
  size?: "sm" | "md" | "lg";
  /** Chart title. */
  title?: string;
  /** Per-level ring configuration. Auto-generated from data depth when omitted. */
  levels?: SunburstLevelConfig[];
  /** Sort order for sibling nodes. @default "desc" */
  sort?: "desc" | "asc" | null;
  /** Sunburst inner/outer radius range. @default ["0%", "90%"] */
  radius?: [string, string];
  /** Which nodes to highlight on hover. @default "descendant" */
  highlightPolicy?: SunburstHighlightPolicy;
  /** Show legend below the chart. @default false */
  showLegend?: boolean;
  /** Custom value formatter for labels and tooltip. */
  valueFormatter?: (v: number) => string;
  /** Animate on mount. @default true */
  animate?: boolean;
  /** Callback fired when a node is clicked. */
  onNodeClick?: (params: { name: string; value: number; data: unknown }) => void;
  /** Additional class name. */
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const SIZE_HEIGHT: Record<"sm" | "md" | "lg", number> = { sm: 200, md: 300, lg: 400 };

const DEFAULT_PALETTE = [
  "#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#06b6d4",
  "#8b5cf6", "#ec4899", "#14b8a6", "#f97316", "#6366f1",
];

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const escapeHtml = (t: string): string =>
  t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/**
 * Compute the maximum depth of a sunburst tree by DFS traversal.
 * Root level (the passed-in array) = depth 0.
 */
function computeMaxDepth(nodes: SunburstNode[], current = 0): number {
  let max = current;
  for (const node of nodes) {
    if (node.children && node.children.length > 0) {
      const childDepth = computeMaxDepth(node.children, current + 1);
      if (childDepth > max) max = childDepth;
    }
  }
  return max;
}

/**
 * Auto-generate level configs based on the data tree depth.
 * Distributes the available radius range evenly across levels.
 * Deeper levels get smaller labels to reduce visual clutter.
 */
function autoLevels(maxDepth: number, radius: [string, string]): SunburstLevelConfig[] {
  const totalLevels = maxDepth + 1;
  const innerPct = parseFloat(radius[0]) || 0;
  const outerPct = parseFloat(radius[1]) || 90;
  const range = outerPct - innerPct;
  const step = range / totalLevels;

  const levels: SunburstLevelConfig[] = [];
  for (let i = 0; i < totalLevels; i++) {
    const r0 = innerPct + step * i;
    const r1 = innerPct + step * (i + 1);
    levels.push({
      r0: `${r0.toFixed(1)}%`,
      r1: `${r1.toFixed(1)}%`,
      itemStyle: {
        borderWidth: 2,
        borderColor: "var(--bg-surface, #ffffff)",
      },
      label: {
        show: i < 3,
        fontSize: Math.max(9, 12 - i),
        rotate: i === 0 ? 0 : "tangential",
      },
    });
  }
  return levels;
}

/**
 * Map highlightPolicy prop to the ECharts emphasis.focus value.
 */
function resolveHighlightFocus(policy: SunburstHighlightPolicy): string | undefined {
  switch (policy) {
    case "descendant": return "descendant";
    case "ancestor": return "ancestor";
    case "self": return "self";
    case "none": return undefined;
    default: return "descendant";
  }
}

/**
 * Assign default palette colors to top-level nodes that lack
 * an explicit itemStyle.color.
 */
function colorizeTopLevel(data: SunburstNode[]): SunburstNode[] {
  return data.map((node, i) => {
    if (node.itemStyle?.color) return node;
    return {
      ...node,
      itemStyle: {
        ...node.itemStyle,
        color: DEFAULT_PALETTE[i % DEFAULT_PALETTE.length],
      },
    };
  });
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export const SunburstChart = React.forwardRef<HTMLDivElement, SunburstChartProps>(
  function SunburstChart(
    {
      data,
      size = "md",
      title,
      levels: levelsProp,
      sort = "desc",
      radius = ["0%", "90%"],
      highlightPolicy = "descendant",
      showLegend = false,
      valueFormatter,
      animate = true,
      onNodeClick,
      className,
      ...rest
    },
    forwardedRef,
  ) {
    const height = SIZE_HEIGHT[size];
    const isEmpty = !data || data.length === 0;
    const fmt = valueFormatter ?? formatCompact;

    const theme = useMemo(() => buildDesignLabEChartsTheme(), []);

    const option = useMemo((): EChartsOption | null => {
      if (isEmpty) return null;

      const coloredData = colorizeTopLevel(data);
      const maxDepth = computeMaxDepth(coloredData);
      const levels = levelsProp ?? autoLevels(maxDepth, radius);
      const focusValue = resolveHighlightFocus(highlightPolicy);

      return {
        animation: animate,
        animationDuration: animate ? 500 : 0,
        animationEasing: "cubicOut",
        title: title
          ? {
              text: escapeHtml(title),
              left: "center",
              textStyle: { fontSize: 16, fontWeight: 600 },
            }
          : undefined,
        tooltip: {
          trigger: "item",
          confine: true,
          formatter: (params: unknown) => {
            const p = params as {
              name: string;
              value: number;
              treePathInfo: Array<{ name: string }>;
            };
            const path = p.treePathInfo
              ? p.treePathInfo
                  .map((n) => n.name)
                  .filter(Boolean)
                  .join(" > ")
              : p.name;
            return `<b>${escapeHtml(path)}</b><br/>${fmt(p.value)}`;
          },
        },
        legend: {
          show: showLegend,
          bottom: 0,
          icon: "roundRect",
          itemWidth: 12,
          itemHeight: 8,
          textStyle: { fontSize: 12 },
          data: coloredData.map((n) => n.name),
        },
        series: [
          {
            type: "sunburst" as const,
            data: coloredData,
            radius,
            sort: sort === null ? undefined : sort,
            levels: levels.map((lvl) => ({
              r0: lvl.r0,
              r1: lvl.r1,
              itemStyle: lvl.itemStyle ?? {
                borderWidth: 2,
                borderColor: "var(--bg-surface, #ffffff)",
              },
              label: lvl.label ?? { show: true, fontSize: 11 },
            })),
            label: {
              show: true,
              formatter: (params: { name: string; value: number }) => {
                if (!params.name) return "";
                return `${params.name}\n${fmt(params.value)}`;
              },
              fontSize: 11,
            },
            emphasis: {
              focus: focusValue,
              itemStyle: {
                shadowBlur: 10,
                shadowColor: "rgba(0, 0, 0, 0.2)",
              },
            },
            itemStyle: {
              borderWidth: 2,
              borderColor: "var(--bg-surface, #ffffff)",
            },
            cursor: onNodeClick ? "pointer" : "default",
          },
        ],
        aria: {
          enabled: true,
          label: {
            description: title
              ? `Sunburst chart: ${escapeHtml(title)}`
              : "Sunburst chart",
          },
        },
      } as EChartsOption;
    }, [
      data, size, title, levelsProp, sort, radius,
      highlightPolicy, showLegend, fmt,
      animate, onNodeClick, isEmpty,
    ]);

    const handleClick = useCallback(
      (params: unknown) => {
        if (!onNodeClick) return;
        const p = params as { name: string; value: number; data: unknown };
        onNodeClick({ name: p.name, value: p.value, data: p.data });
      },
      [onNodeClick],
    );

    const { containerRef } = useEChartsRenderer({
      option: option ?? ({} as EChartsOption),
      theme,
      respectReducedMotion: true,
      onClick: onNodeClick ? handleClick : undefined,
    });

    const setRefs = useCallback(
      (node: HTMLDivElement | null) => {
        (containerRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
        if (typeof forwardedRef === "function") forwardedRef(node);
        else if (forwardedRef)
          (forwardedRef as React.MutableRefObject<HTMLDivElement | null>).current = node;
      },
      [forwardedRef, containerRef],
    );

    /* ---- empty state ---- */
    if (isEmpty) {
      return (
        <div
          ref={forwardedRef}
          className={cn(
            "inline-flex items-center justify-center text-sm text-[var(--text-secondary)]",
            className,
          )}
          style={{ height }}
          role="img"
          aria-label={title ?? "Sunburst chart -- no data"}
          data-testid="sunburst-chart-empty"
          {...rest}
        >
          Veri yok
        </div>
      );
    }

    return (
      <div
        ref={setRefs}
        className={cn("w-full", className)}
        style={{ height, width: "100%" }}
        role="img"
        aria-label={
          title
            ? `Sunburst chart: ${escapeHtml(title)}`
            : "Sunburst chart"
        }
        data-testid="sunburst-chart"
        {...rest}
      />
    );
  },
);

SunburstChart.displayName = "SunburstChart";

export default SunburstChart;
