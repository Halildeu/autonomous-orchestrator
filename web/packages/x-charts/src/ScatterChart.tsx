/**
 * ScatterChart — ECharts-powered scatter/bubble chart with Design Lab integration
 *
 * Backwards-compatible with the AG Charts API surface.
 * Uses the centralized useEChartsRenderer hook for lifecycle management.
 *
 * @migration AG Charts → ECharts (P1, chart-viz-engine-selection D-001)
 */
import React, { useMemo, useCallback } from "react";
import { cn } from "@mfe/design-system";
import { useEChartsRenderer } from "./renderers";
import { formatCompact } from "./utils/formatters";
import { sanitizeNumber } from "./utils/data-validation";
import type { EChartsOption } from "./renderers/echarts-imports";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type ScatterDataPoint = {
  x: number;
  y: number;
  size?: number;
  label?: string;
  color?: string;
};

export type ChartSize = "sm" | "md" | "lg";

export interface ScatterChartProps {
  /** Data points for the scatter plot. */
  data: ScatterDataPoint[];
  /** Visual size variant. @default "md" */
  size?: ChartSize;
  /** Show grid lines. @default true */
  showGrid?: boolean;
  /** Show legend below the chart. @default false */
  showLegend?: boolean;
  /** Chart title. */
  title?: string;
  /** Accessible description. */
  description?: string;
  /** Override default chart colors. */
  colors?: string[];
  /** Custom value formatter for axis labels. */
  valueFormatter?: (value: number) => string;
  /** Animate on mount. @default true */
  animate?: boolean;
  /** Additional class name. */
  className?: string;
  /** X-axis label. */
  xLabel?: string;
  /** Y-axis label. */
  yLabel?: string;
  /** Enable bubble mode — sizes markers by the `size` field. @default false */
  bubble?: boolean;
  /** Text shown when data is empty. @default "Veri yok" */
  noDataText?: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const SIZE_HEIGHT: Record<ChartSize, number> = { sm: 200, md: 300, lg: 400 };

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const getCSSVar = (v: string, fb: string): string => {
  if (typeof document === "undefined") return fb;
  return getComputedStyle(document.documentElement).getPropertyValue(v).trim() || fb;
};

const escapeHtml = (t: string): string =>
  t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const getDefaultPalette = (): string[] => [
  getCSSVar("--action-primary", "#3b82f6"),
  getCSSVar("--state-success-text", "#22c55e"),
  getCSSVar("--state-warning-text", "#f59e0b"),
  getCSSVar("--state-error-text", "#ef4444"),
  getCSSVar("--state-info-text", "#06b6d4"),
  getCSSVar("--action-secondary", "#8b5cf6"),
  "#ec4899", "#14b8a6", "#f97316", "#6366f1",
];

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export const ScatterChart = React.forwardRef<HTMLDivElement, ScatterChartProps>(
  function ScatterChart(
    {
      data,
      size = "md",
      showGrid = true,
      showLegend = false,
      title,
      description,
      colors,
      valueFormatter,
      animate = true,
      className,
      xLabel,
      yLabel,
      bubble = false,
      noDataText = "Veri yok",
      ...rest
    },
    forwardedRef,
  ) {
    const height = SIZE_HEIGHT[size];
    const safeData = useMemo(() =>
      (data ?? []).map(d => ({
        ...d,
        x: sanitizeNumber(d.x),
        y: sanitizeNumber(d.y),
        size: d.size != null ? sanitizeNumber(d.size) : undefined,
      })),
      [data],
    );
    const isEmpty = safeData.length === 0;
    const fmt = valueFormatter ?? formatCompact;

    const option = useMemo((): EChartsOption | null => {
      if (isEmpty) return null;

      const palette = colors ?? getDefaultPalette();
      const fontFamily = getCSSVar("--font-family-sans", "Inter, system-ui, sans-serif");
      const textPrimary = getCSSVar("--text-primary", "#1a1a2e");
      const textSecondary = getCSSVar("--text-secondary", "#6b7280");
      const borderDefault = getCSSVar("--border-default", "#e5e7eb");
      const bgMuted = getCSSVar("--bg-muted", "#f9fafb");

      // Transform data: [x, y, size?, label?, color?]
      const scatterData = safeData.map((d, i) => ({
        value: bubble && d.size != null ? [d.x, d.y, d.size] : [d.x, d.y],
        name: d.label ?? `Point ${i + 1}`,
        itemStyle: d.color ? { color: d.color } : undefined,
      }));

      // Bubble: symbolSize maps size field to visual radius
      const symbolSizeFn = bubble
        ? (val: number[]) => {
            const raw = val[2] ?? 10;
            return Math.max(6, Math.min(60, Math.sqrt(raw) * 4));
          }
        : 8;

      return {
        animation: animate,
        animationDuration: animate ? 500 : 0,
        animationEasing: "cubicOut",
        title: title
          ? {
              text: escapeHtml(title),
              subtext: description ? escapeHtml(description) : undefined,
              left: "center",
              textStyle: { fontFamily, color: textPrimary, fontSize: 16, fontWeight: 600 },
              subtextStyle: { fontFamily, color: textSecondary, fontSize: 13 },
            }
          : undefined,
        tooltip: {
          trigger: "item",
          confine: true,
          textStyle: { fontFamily, fontSize: 13 },
          formatter: (params: unknown) => {
            const p = params as { value: number[]; name: string };
            const xVal = fmt(p.value[0]);
            const yVal = fmt(p.value[1]);
            const label = p.name && !p.name.startsWith("Point ") ? ` — ${escapeHtml(p.name)}` : "";
            return `(${escapeHtml(xVal)}, ${escapeHtml(yVal)})${label}`;
          },
        },
        legend: {
          show: showLegend,
          bottom: 0,
          textStyle: { fontFamily, color: textPrimary, fontSize: 12 },
          icon: "circle",
          itemWidth: 10,
          itemHeight: 10,
        },
        grid: {
          top: title ? 60 : 24,
          right: 16,
          bottom: showLegend ? 48 : 24,
          left: 16,
          containLabel: true,
        },
        xAxis: {
          type: "value",
          name: xLabel,
          nameLocation: "center",
          nameGap: 28,
          nameTextStyle: { fontFamily, color: textSecondary, fontSize: 12 },
          axisLine: { lineStyle: { color: borderDefault } },
          axisTick: { lineStyle: { color: borderDefault } },
          axisLabel: {
            color: textSecondary,
            fontFamily,
            fontSize: 11,
            formatter: (v: number) => fmt(v),
          },
          splitLine: {
            show: showGrid,
            lineStyle: { color: bgMuted, type: "dashed" as const },
          },
        },
        yAxis: {
          type: "value",
          name: yLabel,
          nameLocation: "center",
          nameGap: 40,
          nameTextStyle: { fontFamily, color: textSecondary, fontSize: 12 },
          axisLine: { show: false },
          axisTick: { show: false },
          axisLabel: {
            color: textSecondary,
            fontFamily,
            fontSize: 11,
            formatter: (v: number) => fmt(v),
          },
          splitLine: {
            show: showGrid,
            lineStyle: { color: bgMuted, type: "dashed" as const },
          },
        },
        series: [
          {
            type: "scatter",
            data: scatterData,
            symbolSize: symbolSizeFn,
            itemStyle: {
              color: palette[0],
            },
            emphasis: {
              focus: "self",
              itemStyle: { shadowBlur: 10, shadowColor: "rgba(0,0,0,0.2)" },
            },
          },
        ],
        aria: {
          enabled: true,
          label: {
            description: description
              ? escapeHtml(description)
              : title
                ? `Scatter chart: ${escapeHtml(title)}`
                : "Scatter chart",
          },
        },
      } as EChartsOption;
    }, [data, showGrid, showLegend, valueFormatter, animate, colors, title, description, xLabel, yLabel, bubble, isEmpty]);

    // Use centralized renderer hook
    const { containerRef, isReady } = useEChartsRenderer({
      option: option ?? ({} as EChartsOption),
      respectReducedMotion: true,
    });

    // Merge refs
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
          aria-label={title ?? "Scatter chart — no data"}
          data-testid="scatter-chart-empty"
          {...rest}
        >
          {noDataText}
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
          description
            ? escapeHtml(description)
            : title
              ? `Scatter chart: ${escapeHtml(title)}`
              : "Scatter chart"
        }
        data-testid="scatter-chart"
        {...rest}
      />
    );
  },
);

ScatterChart.displayName = "ScatterChart";

export default ScatterChart;
