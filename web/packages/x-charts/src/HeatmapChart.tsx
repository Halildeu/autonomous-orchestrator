/**
 * HeatmapChart -- ECharts-powered heatmap grid
 *
 * Supports both tuple and object data formats, auto-detected min/max,
 * continuous visual mapping, value labels, and custom cell sizing.
 * Uses the centralized useEChartsRenderer hook for lifecycle management.
 *
 * @migration AG Charts -> ECharts (P3)
 */
import React, { useMemo, useCallback } from "react";
import { cn } from "@mfe/design-system";
import { useEChartsRenderer } from "./renderers";
import { buildDesignLabEChartsTheme } from "./theme/DesignLabEChartsTheme";
import { formatCompact } from "./utils/formatters";
import { sanitizeNumber } from "./utils/data-validation";
import type { EChartsOption } from "./renderers/echarts-imports";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type ChartSize = "sm" | "md" | "lg";

export type HeatmapTupleData = [number, number, number];

export type HeatmapObjectData = {
  x: number | string;
  y: number | string;
  value: number;
};

export interface HeatmapChartProps {
  /** Heatmap data in tuple [x, y, value] or object format. */
  data: HeatmapTupleData[] | HeatmapObjectData[];
  /** X-axis category labels. */
  xLabels?: string[];
  /** Y-axis category labels. */
  yLabels?: string[];
  /** Visual size variant. @default "md" */
  size?: ChartSize;
  /** Chart title. */
  title?: string;
  /** Minimum data value for color scale. Auto-detected if not provided. */
  min?: number;
  /** Maximum data value for color scale. Auto-detected if not provided. */
  max?: number;
  /** Color gradient endpoints [low, high]. @default ['#f5f5f5', '#3b82f6'] */
  colors?: [string, string];
  /** Show value text on each cell. @default false */
  showValues?: boolean;
  /** Custom formatter for cell value display. */
  valueFormatter?: (v: number) => string;
  /** Cell size override; "auto" fits to container. @default "auto" */
  cellSize?: number | "auto";
  /** Show visual map legend. @default true */
  showLegend?: boolean;
  /** Animate on mount. @default true */
  animate?: boolean;
  /** Callback fired when a cell is clicked. */
  onCellClick?: (params: { x: number; y: number; value: number }) => void;
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
 * Type guard: check if data items are object format (have 'x' key).
 */
function isObjectData(
  data: HeatmapTupleData[] | HeatmapObjectData[],
): data is HeatmapObjectData[] {
  return data.length > 0 && typeof data[0] === "object" && !Array.isArray(data[0]) && "x" in data[0];
}

/**
 * Normalize heterogeneous input data into uniform [xIndex, yIndex, value] tuples,
 * and extract xLabels / yLabels when they are not explicitly provided.
 */
function normalizeData(
  data: HeatmapTupleData[] | HeatmapObjectData[],
  xLabels?: string[],
  yLabels?: string[],
): {
  normalized: [number, number, number][];
  xCats: string[];
  yCats: string[];
  dataMin: number;
  dataMax: number;
} {
  if (isObjectData(data)) {
    // Object format: extract unique labels if not provided
    const xSet = xLabels ?? [...new Set(data.map((d) => String(d.x)))];
    const ySet = yLabels ?? [...new Set(data.map((d) => String(d.y)))];

    const normalized: [number, number, number][] = data.map((d) => [
      xSet.indexOf(String(d.x)),
      ySet.indexOf(String(d.y)),
      d.value,
    ]);

    const values = data.map((d) => d.value);
    return {
      normalized,
      xCats: xSet,
      yCats: ySet,
      dataMin: Math.min(...values),
      dataMax: Math.max(...values),
    };
  }

  // Tuple format: [x, y, value] — use labels if provided
  const tuples = data as HeatmapTupleData[];
  const xCats = xLabels ?? [...new Set(tuples.map((t) => String(t[0])))];
  const yCats = yLabels ?? [...new Set(tuples.map((t) => String(t[1])))];
  const values = tuples.map((t) => t[2]);

  // If string labels were provided, remap numeric indices
  const normalized: [number, number, number][] = xLabels
    ? tuples.map((t) => [t[0], t[1], t[2]])
    : tuples;

  return {
    normalized,
    xCats,
    yCats,
    dataMin: Math.min(...values),
    dataMax: Math.max(...values),
  };
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export const HeatmapChart = React.forwardRef<HTMLDivElement, HeatmapChartProps>(
  function HeatmapChart(
    {
      data,
      xLabels,
      yLabels,
      size = "md",
      title,
      min: minProp,
      max: maxProp,
      colors = ["#f5f5f5", "#3b82f6"],
      showValues = false,
      valueFormatter,
      cellSize = "auto",
      showLegend = true,
      animate = true,
      onCellClick,
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

      const { normalized, xCats, yCats, dataMin, dataMax } =
        normalizeData(data, xLabels, yLabels);

      const effectiveMin = minProp ?? dataMin;
      const effectiveMax = maxProp ?? dataMax;

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
          formatter: (params: { data: [number, number, number] }) => {
            const [xi, yi, val] = params.data;
            const xLabel = xCats[xi] ?? String(xi);
            const yLabel = yCats[yi] ?? String(yi);
            const display = escapeHtml(fmt(sanitizeNumber(val)));
            return `${escapeHtml(xLabel)} / ${escapeHtml(yLabel)}<br/><strong>${display}</strong>`;
          },
        },
        grid: {
          top: title ? 56 : 20,
          right: showLegend ? 80 : 16,
          bottom: 24,
          left: 16,
          containLabel: true,
        },
        xAxis: {
          type: "category" as const,
          data: xCats,
          splitArea: { show: true },
          axisLabel: { fontSize: 11 },
          axisTick: { alignWithLabel: true },
        },
        yAxis: {
          type: "category" as const,
          data: yCats,
          splitArea: { show: true },
          axisLabel: { fontSize: 11 },
        },
        visualMap: {
          min: effectiveMin,
          max: effectiveMax,
          calculable: true,
          show: showLegend,
          orient: "vertical" as const,
          right: 0,
          top: "center",
          inRange: {
            color: colors,
          },
          textStyle: { fontSize: 11 },
        },
        series: [
          {
            type: "heatmap" as const,
            data: normalized,
            label: {
              show: showValues,
              fontSize: 10,
              formatter: (params: { value: [number, number, number] }) =>
                escapeHtml(fmt(sanitizeNumber(params.value[2]))),
            },
            emphasis: {
              itemStyle: {
                borderColor: "#333",
                borderWidth: 2,
                shadowBlur: 8,
                shadowColor: "rgba(0,0,0,0.25)",
              },
            },
            ...(cellSize !== "auto" ? { itemStyle: { width: cellSize, height: cellSize } } : {}),
          },
        ],
        aria: {
          enabled: true,
          label: {
            description: title
              ? `Heatmap chart: ${escapeHtml(title)}`
              : "Heatmap chart",
          },
        },
      } as EChartsOption;
    }, [
      data, xLabels, yLabels, title, minProp, maxProp,
      colors, showValues, fmt, cellSize,
      showLegend, animate, isEmpty,
    ]);

    const handleClick = useCallback(
      (params: unknown) => {
        if (!onCellClick) return;
        const p = params as { data: [number, number, number] };
        if (Array.isArray(p.data) && p.data.length >= 3) {
          onCellClick({
            x: p.data[0],
            y: p.data[1],
            value: p.data[2],
          });
        }
      },
      [onCellClick],
    );

    const { containerRef } = useEChartsRenderer({
      option: option ?? ({} as EChartsOption),
      theme,
      respectReducedMotion: true,
      onClick: onCellClick ? handleClick : undefined,
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
          aria-label={title ?? "Heatmap chart -- no data"}
          data-testid="heatmap-chart-empty"
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
            ? `Heatmap chart: ${escapeHtml(title)}`
            : "Heatmap chart"
        }
        data-testid="heatmap-chart"
        {...rest}
      />
    );
  },
);

HeatmapChart.displayName = "HeatmapChart";

export default HeatmapChart;
