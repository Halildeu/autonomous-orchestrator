/**
 * GaugeChart -- ECharts-powered gauge with threshold zones
 *
 * Supports configurable thresholds, pointer styling, progress arcs,
 * and custom value formatting. Uses the centralized useEChartsRenderer
 * hook for lifecycle management.
 *
 * @migration SVG -> ECharts (P3)
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

export type GaugeThreshold = {
  /** Threshold boundary value. */
  value: number;
  /** Color for the zone up to this value. */
  color: string;
  /** Optional label for the zone. */
  label?: string;
};

export interface GaugeChartProps {
  /** Current gauge value. */
  value: number;
  /** Minimum scale value. @default 0 */
  min?: number;
  /** Maximum scale value. @default 100 */
  max?: number;
  /** Title displayed above the gauge. */
  title?: string;
  /** Visual size variant. @default "md" */
  size?: ChartSize;
  /** Threshold zones for colored arc segments. */
  thresholds?: GaugeThreshold[];
  /** Start angle in degrees. @default 225 */
  startAngle?: number;
  /** End angle in degrees. @default -45 */
  endAngle?: number;
  /** Show a progress arc from min to current value. @default false */
  showProgress?: boolean;
  /** Pointer configuration. */
  pointer?: {
    length?: string;
    width?: number;
    color?: string;
  };
  /** Number of segments on the axis. @default 10 */
  splitNumber?: number;
  /** Show numeric axis labels. @default true */
  showAxisLabel?: boolean;
  /** Custom formatter for the center value display. */
  valueFormatter?: (v: number) => string;
  /** Animate on mount and value changes. @default true */
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
 * Normalize threshold values into ECharts axisLine color stops (0-1 range).
 * Each entry is [normalizedPosition, color].
 */
function buildAxisLineColors(
  thresholds: GaugeThreshold[],
  min: number,
  max: number,
): [number, string][] {
  const range = max - min;
  if (range <= 0) return [[1, DEFAULT_PALETTE[0]]];

  const sorted = [...thresholds].sort((a, b) => a.value - b.value);
  return sorted.map((t) => [
    Math.min(Math.max((t.value - min) / range, 0), 1),
    t.color,
  ]);
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export const GaugeChart = React.forwardRef<HTMLDivElement, GaugeChartProps>(
  function GaugeChart(
    {
      value,
      min = 0,
      max = 100,
      title,
      size = "md",
      thresholds,
      startAngle = 225,
      endAngle = -45,
      showProgress = false,
      pointer,
      splitNumber = 10,
      showAxisLabel = true,
      valueFormatter,
      animate = true,
      className,
      ...rest
    },
    forwardedRef,
  ) {
    const height = SIZE_HEIGHT[size];
    const isEmpty = value == null;
    const safeValue = sanitizeNumber(value);
    const fmt = valueFormatter ?? formatCompact;

    const theme = useMemo(() => buildDesignLabEChartsTheme(), []);

    const option = useMemo((): EChartsOption | null => {
      if (isEmpty) return null;

      const axisLineColors = thresholds?.length
        ? buildAxisLineColors(thresholds, min, max)
        : [
            [0.6, "#22c55e"],
            [0.8, "#f59e0b"],
            [1, "#ef4444"],
          ] as [number, string][];

      return {
        animation: animate,
        animationDuration: animate ? 500 : 0,
        animationEasing: "cubicOut",
        series: [
          {
            type: "gauge" as const,
            min,
            max,
            startAngle,
            endAngle,
            splitNumber,
            data: [{ value: safeValue, name: title ?? "" }],
            progress: {
              show: showProgress,
              width: 12,
            },
            axisLine: {
              lineStyle: {
                width: 16,
                color: axisLineColors,
              },
            },
            pointer: {
              length: pointer?.length ?? "60%",
              width: pointer?.width ?? 5,
              itemStyle: pointer?.color
                ? { color: pointer.color }
                : undefined,
            },
            axisTick: {
              show: true,
              distance: -20,
              length: 6,
              lineStyle: { color: "#999", width: 1 },
            },
            splitLine: {
              show: true,
              distance: -24,
              length: 12,
              lineStyle: { color: "#999", width: 2 },
            },
            axisLabel: {
              show: showAxisLabel,
              distance: 30,
              fontSize: 11,
              formatter: (v: number) => escapeHtml(fmt(v)),
            },
            detail: {
              valueAnimation: animate,
              formatter: (v: number) => escapeHtml(fmt(v)),
              fontSize: Math.round(height * 0.08),
              fontWeight: 600,
              offsetCenter: [0, "40%"],
              color: "inherit",
            },
            title: title
              ? {
                  show: true,
                  offsetCenter: [0, "60%"],
                  fontSize: 13,
                  color: "var(--text-secondary, #666)",
                }
              : { show: false },
          },
        ],
        aria: {
          enabled: true,
          label: {
            description: title
              ? `Gauge chart: ${escapeHtml(title)}`
              : "Gauge chart",
          },
        },
      } as EChartsOption;
    }, [
      value, min, max, title, thresholds, startAngle, endAngle,
      showProgress, pointer, splitNumber, showAxisLabel,
      fmt, animate, height, isEmpty,
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
          aria-label={title ?? "Gauge chart -- no data"}
          data-testid="gauge-chart-empty"
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
            ? `Gauge chart: ${escapeHtml(title)}`
            : "Gauge chart"
        }
        data-testid="gauge-chart"
        {...rest}
      />
    );
  },
);

GaugeChart.displayName = "GaugeChart";

export default GaugeChart;
