/**
 * PieChart -- ECharts-powered pie/donut chart
 *
 * Backwards-compatible with the design-system PieChart props API.
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

export interface PieChartProps {
  /** Data points to render as slices. */
  data: ChartDataPoint[];
  /** Visual size variant. @default "md" */
  size?: ChartSize;
  /** Donut mode (ring instead of filled). @default false */
  donut?: boolean;
  /** Show labels beside slices. @default false */
  showLabels?: boolean;
  /** Show legend below the chart. @default false */
  showLegend?: boolean;
  /** Show percentage on slices. @default false */
  showPercentage?: boolean;
  /** Custom value formatter. */
  valueFormatter?: (value: number) => string;
  /** Center content for donut mode. */
  innerLabel?: React.ReactNode;
  /** Animate slices on mount. @default true */
  animate?: boolean;
  /** Chart title. */
  title?: string;
  /** Accessible description. */
  description?: string;
  /** Additional class name. */
  className?: string;
  /** Callback fired when a data point (slice) is clicked. */
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

export const PieChart = React.forwardRef<HTMLDivElement, PieChartProps>(
  function PieChart(
    {
      data,
      size = "md",
      donut = false,
      showLabels = false,
      showLegend = false,
      showPercentage = false,
      valueFormatter,
      innerLabel,
      animate = true,
      title,
      description,
      className,
      onDataPointClick,
      ...rest
    },
    forwardedRef,
  ) {
    const height = SIZE_HEIGHT[size];

    const safeData = useMemo(() => sanitizeDataPoints(data), [data]);
    const validData = useMemo(
      () => safeData.filter((d) => d.value > 0),
      [safeData],
    );

    const isEmpty = validData.length === 0;
    const fmt = valueFormatter ?? formatCompact;

    const theme = useMemo(() => buildDesignLabEChartsTheme(), []);

    const option = useMemo((): EChartsOption | null => {
      if (isEmpty) return null;

      const palette = DEFAULT_PALETTE;

      const pieData = validData.map((d, i) => ({
        name: d.label,
        value: d.value,
        itemStyle: { color: d.color ?? palette[i % palette.length] },
      }));

      const total = validData.reduce((sum, d) => sum + d.value, 0);

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
          trigger: "item",
          confine: true,
          formatter: (params: unknown) => {
            const p = params as { name: string; value: number; percent: number };
            const formatted = fmt(p.value);
            return `${escapeHtml(p.name)}: ${escapeHtml(formatted)} (${p.percent}%)`;
          },
        },
        legend: {
          show: showLegend,
          bottom: 0,
          icon: "circle",
          itemWidth: 10,
          itemHeight: 10,
          textStyle: { fontSize: 12 },
        },
        series: [
          {
            type: "pie",
            radius: donut ? ["45%", "70%"] : ["0%", "70%"],
            center: ["50%", title ? "55%" : "50%"],
            data: pieData,
            label: {
              show: showLabels || showPercentage,
              formatter: showPercentage
                ? (p: { name: string; value: number }) =>
                    `${escapeHtml(p.name)} ${total > 0 ? Math.round((p.value / total) * 100) : 0}%`
                : showLabels
                  ? (p: { name: string }) => escapeHtml(p.name)
                  : undefined,
              fontSize: 12,
            },
            labelLine: { show: showLabels || showPercentage },
            emphasis: {
              itemStyle: {
                shadowBlur: 10,
                shadowColor: "rgba(0,0,0,0.15)",
                shadowOffsetX: 0,
              },
            },
            cursor: onDataPointClick ? "pointer" : "default",
          },
        ],
        aria: {
          enabled: true,
          label: {
            description: description
              ? escapeHtml(description)
              : title
                ? `Pie chart: ${escapeHtml(title)}`
                : "Pie chart",
          },
        },
      } as EChartsOption;
    }, [
      validData, donut, showLabels, showLegend, showPercentage,
      valueFormatter, animate, title, description, onDataPointClick, isEmpty,
    ]);

    const handleClick = useCallback(
      (params: unknown) => {
        if (!onDataPointClick) return;
        const p = params as { name: string; value: number; data: Record<string, unknown> };
        onDataPointClick({
          datum: { ...p.data, label: p.name, value: p.value },
          value: p.value,
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
          aria-label={title ?? "Pie chart -- no data"}
          data-testid="pie-chart-empty"
          {...rest}
        >
          Veri yok
        </div>
      );
    }

    return (
      <div
        ref={setRefs}
        className={cn("relative w-full", className)}
        style={{ height, width: "100%" }}
        role="img"
        aria-label={
          description
            ? escapeHtml(description)
            : title
              ? `Pie chart: ${escapeHtml(title)}`
              : "Pie chart"
        }
        data-testid="pie-chart"
        {...rest}
      >
        {donut && innerLabel ? (
          <div
            className="pointer-events-none absolute inset-0 flex items-center justify-center"
            data-testid="pie-chart-inner-label"
          >
            {innerLabel}
          </div>
        ) : null}
      </div>
    );
  },
);

PieChart.displayName = "PieChart";

export default PieChart;
