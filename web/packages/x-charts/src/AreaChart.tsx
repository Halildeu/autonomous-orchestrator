/**
 * AreaChart -- ECharts-powered area chart
 *
 * Backwards-compatible with the design-system AreaChart props API.
 * Uses the centralized useEChartsRenderer hook for lifecycle management.
 *
 * @migration AG Charts -> ECharts (P3)
 */
import React, { useMemo, useCallback } from "react";
import { cn } from "@mfe/design-system";
import { useEChartsRenderer } from "./renderers";
import { buildDesignLabEChartsTheme } from "./theme/DesignLabEChartsTheme";
import { formatCompact } from "./utils/formatters";
import { sanitizeSeries } from "./utils/data-validation";
import type { EChartsOption } from "./renderers/echarts-imports";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type ChartSize = "sm" | "md" | "lg";

export type ChartSeries = {
  name: string;
  data: number[];
  color?: string;
};

export interface AreaChartProps {
  /** Series to render as filled areas. */
  series: ChartSeries[];
  /** X-axis labels. */
  labels: string[];
  /** Visual size variant. @default "md" */
  size?: ChartSize;
  /** Stack areas on top of each other. @default false */
  stacked?: boolean;
  /** Show dot markers at data points. @default true */
  showDots?: boolean;
  /** Show grid lines. @default true */
  showGrid?: boolean;
  /** Show legend below the chart. @default false */
  showLegend?: boolean;
  /** Use gradient fills instead of flat color. @default true */
  gradient?: boolean;
  /** Use bezier curves instead of straight lines. @default false */
  curved?: boolean;
  /** Custom value formatter. */
  valueFormatter?: (value: number) => string;
  /** Animate on mount. @default true */
  animate?: boolean;
  /** Chart title. */
  title?: string;
  /** Accessible description. */
  description?: string;
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
 * Build a linear gradient definition for ECharts area fills.
 * Goes from `opacity` at the top to 0 at the bottom.
 */
const makeGradient = (color: string, opacity: number) => ({
  type: "linear" as const,
  x: 0, y: 0, x2: 0, y2: 1,
  colorStops: [
    { offset: 0, color: `${color}${Math.round(opacity * 255).toString(16).padStart(2, "0")}` },
    { offset: 1, color: `${color}00` },
  ],
});

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export const AreaChart = React.forwardRef<HTMLDivElement, AreaChartProps>(
  function AreaChart(
    {
      series: seriesData,
      labels,
      size = "md",
      stacked = false,
      showDots = true,
      showGrid = true,
      showLegend = false,
      gradient = true,
      curved = false,
      valueFormatter,
      animate = true,
      title,
      description,
      className,
      ...rest
    },
    forwardedRef,
  ) {
    const height = SIZE_HEIGHT[size];
    const safeSeries = useMemo(() => sanitizeSeries(seriesData), [seriesData]);
    const isEmpty = safeSeries.length === 0 || !labels || labels.length === 0;
    const fmt = valueFormatter ?? formatCompact;

    const theme = useMemo(() => buildDesignLabEChartsTheme(), []);

    const option = useMemo((): EChartsOption | null => {
      if (isEmpty) return null;

      const palette = DEFAULT_PALETTE;

      const echartsSeriesList = safeSeries.map((s, i) => {
        const color = s.color ?? palette[i % palette.length];
        return {
          type: "line" as const,
          name: s.name,
          data: s.data,
          smooth: curved,
          stack: stacked ? "total" : undefined,
          symbol: showDots ? "circle" : "none",
          symbolSize: showDots ? 5 : 0,
          lineStyle: { color, width: 2 },
          itemStyle: { color },
          areaStyle: gradient
            ? { color: makeGradient(color, 0.35) }
            : { color, opacity: 0.6 },
          emphasis: {
            focus: "series" as const,
            itemStyle: { borderWidth: 2 },
          },
        };
      });

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
          valueFormatter: (v: unknown) => fmt(v as number),
        },
        legend: {
          show: showLegend || safeSeries.length > 1,
          bottom: 0,
          icon: "roundRect",
          itemWidth: 12,
          itemHeight: 8,
          textStyle: { fontSize: 12 },
        },
        grid: {
          top: title ? 60 : 24,
          right: 16,
          bottom: showLegend || safeSeries.length > 1 ? 48 : 24,
          left: 16,
          containLabel: true,
        },
        xAxis: {
          type: "category",
          data: labels,
          boundaryGap: false,
          axisLabel: { fontSize: 11 },
        },
        yAxis: {
          type: "value",
          axisLabel: {
            fontSize: 11,
            formatter: (v: number) => fmt(v),
          },
          splitLine: {
            show: showGrid,
            lineStyle: { type: "dashed" as const },
          },
        },
        series: echartsSeriesList,
        aria: {
          enabled: true,
          label: {
            description: description
              ? escapeHtml(description)
              : title
                ? `Area chart: ${escapeHtml(title)}`
                : "Area chart",
          },
        },
      } as EChartsOption;
    }, [
      seriesData, labels, stacked, showDots, showGrid,
      showLegend, gradient, curved, valueFormatter, animate,
      title, description, isEmpty,
    ]);

    const { containerRef } = useEChartsRenderer({
      option: option ?? ({} as EChartsOption),
      theme,
      respectReducedMotion: true,
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
          aria-label={title ?? "Area chart -- no data"}
          data-testid="area-chart-empty"
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
              ? `Area chart: ${escapeHtml(title)}`
              : "Area chart"
        }
        data-testid="area-chart"
        {...rest}
      />
    );
  },
);

AreaChart.displayName = "AreaChart";

export default AreaChart;
