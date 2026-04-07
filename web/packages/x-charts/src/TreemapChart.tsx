/**
 * TreemapChart -- ECharts-powered hierarchical treemap
 *
 * Supports nested data structures with drill-down, breadcrumb navigation,
 * color saturation mapping, and custom value formatting. Uses the
 * centralized useEChartsRenderer hook for lifecycle management.
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

export type ChartSize = "sm" | "md" | "lg";

export type TreemapNode = {
  /** Display name for the node. */
  name: string;
  /** Numeric value determining node area. */
  value?: number;
  /** Nested children for hierarchical data. */
  children?: TreemapNode[];
  /** Per-node style override. */
  itemStyle?: { color?: string };
};

export interface TreemapChartProps {
  /** Hierarchical tree data. */
  data: TreemapNode[];
  /** Visual size variant. @default "md" */
  size?: ChartSize;
  /** Chart title. */
  title?: string;
  /** Show legend below the chart. @default false */
  showLegend?: boolean;
  /** Show breadcrumb navigation on drill-down. @default true */
  showBreadcrumb?: boolean;
  /** Maximum visible depth (1 = only root children). @default 1 */
  leafDepth?: number;
  /** Pan/zoom mode. @default false */
  roam?: boolean | "move" | "scale";
  /** Saturation range for color mapping. @default [0.35, 0.5] */
  colorSaturation?: [number, number];
  /** Minimum area (px^2) to render a label. @default 300 */
  visibleMin?: number;
  /** Custom formatter for displayed values. */
  valueFormatter?: (v: number) => string;
  /** Callback fired when a node is clicked. */
  onNodeClick?: (params: { name: string; value: number; data: unknown }) => void;
  /** Animate on mount. @default true */
  animate?: boolean;
  /** Additional class name. */
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const SIZE_HEIGHT: Record<ChartSize, number> = { sm: 200, md: 300, lg: 400 };

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
 * Compute the maximum depth of the tree to generate the right number
 * of levels configuration (dynamic, not hardcoded).
 */
function getMaxDepth(nodes: TreemapNode[], current = 1): number {
  let maxD = current;
  for (const node of nodes) {
    if (node.children && node.children.length > 0) {
      maxD = Math.max(maxD, getMaxDepth(node.children, current + 1));
    }
  }
  return maxD;
}

/**
 * Build ECharts levels array dynamically based on tree depth.
 * Level 0 = invisible root, levels 1..N = visible depth layers.
 */
function buildLevels(
  depth: number,
  colorSaturation: [number, number],
): Record<string, unknown>[] {
  const levels: Record<string, unknown>[] = [];

  // Level 0 — invisible root
  levels.push({
    itemStyle: {
      borderColor: "#fff",
      borderWidth: 2,
      gapWidth: 2,
    },
  });

  for (let i = 1; i <= depth; i++) {
    const isLeaf = i === depth;
    levels.push({
      colorSaturation,
      itemStyle: {
        borderColor: "#fff",
        borderWidth: isLeaf ? 1 : 2,
        gapWidth: isLeaf ? 1 : 2,
        borderColorSaturation: 0.6,
      },
      upperLabel: {
        show: !isLeaf,
        height: 14,
        fontSize: 10,
        color: "#333",
        padding: [2, 4, 0, 4],
      },
    });
  }

  return levels;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export const TreemapChart = React.forwardRef<HTMLDivElement, TreemapChartProps>(
  function TreemapChart(
    {
      data,
      size = "md",
      title,
      showLegend = false,
      showBreadcrumb = true,
      leafDepth = 1,
      roam = false,
      colorSaturation = [0.35, 0.5],
      visibleMin = 300,
      valueFormatter,
      onNodeClick,
      animate = true,
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

      const maxDepth = getMaxDepth(data);
      const levels = buildLevels(maxDepth, colorSaturation);

      const labelFormatter = (params: { name: string; value: number }) => {
        const formatted = fmt(params.value);
        return `${escapeHtml(params.name)}\n${escapeHtml(formatted)}`;
      };

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
          formatter: (params: { name: string; value: number }) => {
            const val = escapeHtml(fmt(params.value));
            return `<strong>${escapeHtml(params.name)}</strong><br/>${val}`;
          },
        },
        legend: {
          show: showLegend,
          bottom: 0,
          icon: "roundRect",
          itemWidth: 12,
          itemHeight: 8,
          textStyle: { fontSize: 12 },
        },
        series: [
          {
            type: "treemap" as const,
            data,
            leafDepth,
            roam,
            visibleMin,
            label: {
              show: true,
              formatter: labelFormatter,
              fontSize: 12,
              ellipsis: true,
            },
            upperLabel: {
              show: true,
              height: 16,
              fontSize: 11,
              color: "#333",
              padding: [2, 4, 0, 4],
            },
            breadcrumb: {
              show: showBreadcrumb,
              left: "center",
              bottom: showLegend ? 28 : 4,
              itemStyle: {
                textStyle: { fontSize: 11 },
              },
            },
            levels,
            itemStyle: {
              borderColor: "#fff",
              borderWidth: 1,
              gapWidth: 1,
            },
            colorMappingBy: "id",
            emphasis: {
              itemStyle: {
                borderColor: "#333",
                borderWidth: 1,
              },
            },
          },
        ],
        color: DEFAULT_PALETTE,
        aria: {
          enabled: true,
          label: {
            description: title
              ? `Treemap chart: ${escapeHtml(title)}`
              : "Treemap chart",
          },
        },
      } as EChartsOption;
    }, [
      data, title, showLegend, showBreadcrumb, leafDepth,
      roam, colorSaturation, visibleMin, fmt,
      animate, isEmpty,
    ]);

    const handleClick = useCallback(
      (params: unknown) => {
        if (!onNodeClick) return;
        const p = params as { name: string; value: number; data: unknown };
        onNodeClick({
          name: p.name,
          value: typeof p.value === "number" ? p.value : 0,
          data: p.data,
        });
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
          aria-label={title ?? "Treemap chart -- no data"}
          data-testid="treemap-chart-empty"
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
            ? `Treemap chart: ${escapeHtml(title)}`
            : "Treemap chart"
        }
        data-testid="treemap-chart"
        {...rest}
      />
    );
  },
);

TreemapChart.displayName = "TreemapChart";

export default TreemapChart;
