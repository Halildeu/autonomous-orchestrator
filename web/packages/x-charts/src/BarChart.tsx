/**
 * BarChart -- ECharts-powered bar chart
 *
 * Backwards-compatible with the design-system BarChart props API.
 * Uses the centralized useEChartsRenderer hook for lifecycle management.
 *
 * @migration AG Charts -> ECharts (P3)
 */
import React, { useMemo, useCallback } from "react";
import { cn } from "@mfe/design-system";
import { useEChartsRenderer } from "./renderers";
import { buildDesignLabEChartsTheme } from "./theme/DesignLabEChartsTheme";
import { formatCompact } from "./utils/formatters";
import { sanitizeDataPoints } from "./utils/data-validation";
import type { EChartsOption } from "./renderers/echarts-imports";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type ChartSize = "sm" | "md" | "lg";

export type ChartDataPoint = {
  label: string;
  value: number;
  color?: string;
};

export type ChartClickEvent = {
  datum: Record<string, unknown>;
  value?: number;
  label?: string;
};

export interface BarChartProps {
  /** Data points to render as bars. */
  data: ChartDataPoint[];
  /** Bar orientation. @default "vertical" */
  orientation?: "vertical" | "horizontal";
  /** Visual size variant. @default "md" */
  size?: ChartSize;
  /** Show value labels on bars. @default false */
  showValues?: boolean;
  /** Show grid lines. @default true */
  showGrid?: boolean;
  /** Show legend below the chart. @default false */
  showLegend?: boolean;
  /** Custom value formatter. */
  valueFormatter?: (value: number) => string;
  /** Animate bars on mount. @default true */
  animate?: boolean;
  /** Override default chart colors. */
  colors?: string[];
  /** Chart title. */
  title?: string;
  /** Accessible description. */
  description?: string;
  /** Additional class name. */
  className?: string;
  /** Multi-series: grouped bars by field. */
  series?: { field: string; name: string; color?: string }[];
  /** Callback fired when a data point (bar) is clicked. */
  onDataPointClick?: (event: ChartClickEvent) => void;
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

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export const BarChart = React.forwardRef<HTMLDivElement, BarChartProps>(
  function BarChart(
    {
      data,
      orientation = "vertical",
      size = "md",
      showValues = false,
      showGrid = true,
      showLegend = false,
      valueFormatter,
      animate = true,
      colors,
      title,
      description,
      className,
      series: seriesDef,
      onDataPointClick,
      ...rest
    },
    forwardedRef,
  ) {
    const height = SIZE_HEIGHT[size];
    const safeData = useMemo(() => sanitizeDataPoints(data), [data]);
    const isEmpty = safeData.length === 0;
    const isHorizontal = orientation === "horizontal";
    const hasMultiSeries = seriesDef && seriesDef.length > 0;
    const fmt = valueFormatter ?? formatCompact;

    const theme = useMemo(() => buildDesignLabEChartsTheme(), []);

    const option = useMemo((): EChartsOption | null => {
      if (isEmpty) return null;

      const palette = colors ?? DEFAULT_PALETTE;

      const categoryAxis = {
        type: "category" as const,
        data: safeData.map((d) => d.label),
        axisLabel: { fontSize: 11 },
        axisTick: { alignWithLabel: true },
      };

      const valueAxis = {
        type: "value" as const,
        axisLabel: {
          fontSize: 11,
          formatter: (v: number) => fmt(v),
        },
        splitLine: {
          show: showGrid,
          lineStyle: { type: "dashed" as const },
        },
      };

      const echartsSeriesList = hasMultiSeries
        ? seriesDef!.map((s, i) => ({
            type: "bar" as const,
            name: s.name,
            data: safeData.map((d) => (d as Record<string, unknown>)[s.field] as number ?? 0),
            itemStyle: { color: s.color ?? palette[i % palette.length] },
            label: showValues
              ? {
                  show: true,
                  position: isHorizontal ? "right" : "top" as const,
                  formatter: valueFormatter
                    ? (p: { value: number }) => fmt(p.value)
                    : undefined,
                  fontSize: 11,
                }
              : { show: false },
            cursor: onDataPointClick ? "pointer" : "default",
          }))
        : [
            {
              type: "bar" as const,
              name: title ?? "Value",
              data: safeData.map((d, i) => ({
                value: d.value,
                itemStyle: { color: d.color ?? palette[i % palette.length] },
              })),
              label: showValues
                ? {
                    show: true,
                    position: isHorizontal ? ("right" as const) : ("top" as const),
                    formatter: valueFormatter
                      ? (p: { value: number }) => fmt(p.value)
                      : undefined,
                    fontSize: 11,
                  }
                : { show: false },
              cursor: onDataPointClick ? "pointer" : "default",
            },
          ];

      return {
        animation: animate,
        animationDuration: animate ? 500 : 0,
        animationEasing: "cubicOut",
        title: title
          ? {
              text: escapeHtml(title),
              subtext: description ? escapeHtml(description) : undefined,
              left: "center",
              textStyle: { fontSize: 16, fontWeight: 600 },
              subtextStyle: { fontSize: 13 },
            }
          : undefined,
        tooltip: {
          trigger: "axis",
          confine: true,
          axisPointer: { type: "shadow" },
          valueFormatter: (v: unknown) => fmt(v as number),
        },
        legend: {
          show: showLegend || hasMultiSeries,
          bottom: 0,
          icon: "roundRect",
          itemWidth: 12,
          itemHeight: 8,
          textStyle: { fontSize: 12 },
        },
        grid: {
          top: title ? 60 : 24,
          right: 16,
          bottom: showLegend || hasMultiSeries ? 48 : 24,
          left: 16,
          containLabel: true,
        },
        xAxis: isHorizontal ? valueAxis : categoryAxis,
        yAxis: isHorizontal ? categoryAxis : valueAxis,
        series: echartsSeriesList,
        aria: {
          enabled: true,
          label: {
            description: description
              ? escapeHtml(description)
              : title
                ? `Bar chart: ${escapeHtml(title)}`
                : "Bar chart",
          },
        },
      } as EChartsOption;
    }, [
      data, orientation, showValues, showGrid, showLegend,
      valueFormatter, animate, colors, title, description,
      seriesDef, onDataPointClick, isEmpty, isHorizontal, hasMultiSeries,
    ]);

    const handleClick = useCallback(
      (params: unknown) => {
        if (!onDataPointClick) return;
        const p = params as { data: unknown; name: string; value: number; dataIndex: number };
        const raw = typeof p.data === "object" && p.data !== null ? p.data as Record<string, unknown> : {};
        onDataPointClick({
          datum: { ...raw, label: p.name, value: p.value },
          value: typeof p.value === "number" ? p.value : (raw.value as number),
          label: p.name,
        });
      },
      [onDataPointClick],
    );

    const { containerRef } = useEChartsRenderer({
      option: option ?? ({} as EChartsOption),
      theme,
      respectReducedMotion: true,
      onClick: onDataPointClick ? handleClick : undefined,
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
          aria-label={title ?? "Bar chart -- no data"}
          data-testid="bar-chart-empty"
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
          description
            ? escapeHtml(description)
            : title
              ? `Bar chart: ${escapeHtml(title)}`
              : "Bar chart"
        }
        data-testid="bar-chart"
        {...rest}
      />
    );
  },
);

BarChart.displayName = "BarChart";

export default BarChart;
