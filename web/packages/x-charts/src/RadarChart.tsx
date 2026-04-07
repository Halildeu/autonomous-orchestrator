/**
 * RadarChart -- ECharts-powered radar / spider chart
 *
 * Supports multiple series overlays, polygon or circle shapes,
 * area fills, and custom axis indicators. Uses the centralized
 * useEChartsRenderer hook for lifecycle management.
 *
 * @migration SVG -> ECharts (P3)
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

export type RadarIndicator = {
  /** Axis name displayed at the spoke end. */
  name: string;
  /** Maximum value for this axis. */
  max: number;
};

export type RadarSeriesItem = {
  /** Series legend name. */
  name: string;
  /** Data values matching indicator order. */
  data: number[];
  /** Override color for this series. */
  color?: string;
  /** Per-series area style override. */
  areaStyle?: { opacity?: number };
};

export interface RadarChartProps {
  /** Axis indicators defining the radar shape. */
  indicators: RadarIndicator[];
  /** Data series to plot on the radar. */
  series: RadarSeriesItem[];
  /** Visual size variant. @default "md" */
  size?: ChartSize;
  /** Radar shape. @default "polygon" */
  shape?: "polygon" | "circle";
  /** Fill the area under each series line. @default false */
  showArea?: boolean;
  /** Show axis name labels. @default true */
  showLabels?: boolean;
  /** Show legend below the chart. @default false */
  showLegend?: boolean;
  /** Number of concentric split rings. @default 5 */
  splitNumber?: number;
  /** Chart title. */
  title?: string;
  /** Animate on mount. @default true */
  animate?: boolean;
  /** Custom value formatter for tooltip. */
  valueFormatter?: (v: number) => string;
  /** Callback fired when a data point is clicked. */
  onDataPointClick?: (params: unknown) => void;
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

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export const RadarChart = React.forwardRef<HTMLDivElement, RadarChartProps>(
  function RadarChart(
    {
      indicators,
      series,
      size = "md",
      shape = "polygon",
      showArea = false,
      showLabels = true,
      showLegend = false,
      splitNumber = 5,
      title,
      valueFormatter,
      animate = true,
      onDataPointClick,
      className,
      ...rest
    },
    forwardedRef,
  ) {
    const height = SIZE_HEIGHT[size];
    const isEmpty = !indicators || indicators.length === 0 || !series || series.length === 0;
    const fmt = valueFormatter ?? formatCompact;

    const theme = useMemo(() => buildDesignLabEChartsTheme(), []);

    const option = useMemo((): EChartsOption | null => {
      if (isEmpty) return null;

      const radarData = series.map((s, idx) => {
        const seriesColor = s.color ?? DEFAULT_PALETTE[idx % DEFAULT_PALETTE.length];

        // Determine area style: per-series override > global showArea > none
        let areaConfig: { color: string; opacity: number } | undefined;
        if (s.areaStyle) {
          areaConfig = {
            color: seriesColor,
            opacity: s.areaStyle.opacity ?? 0.2,
          };
        } else if (showArea) {
          areaConfig = {
            color: seriesColor,
            opacity: 0.15,
          };
        }

        return {
          value: s.data,
          name: s.name,
          lineStyle: { color: seriesColor, width: 2 },
          itemStyle: { color: seriesColor },
          areaStyle: areaConfig,
        };
      });

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
            const p = params as { name: string; value: number[] };
            const header = `<b>${escapeHtml(p.name)}</b>`;
            const lines = indicators.map((ind, i) => {
              const val = p.value?.[i] ?? 0;
              return `${escapeHtml(ind.name)}: ${fmt(val)}`;
            });
            return `${header}<br/>${lines.join("<br/>")}`;
          },
        },
        legend: {
          show: showLegend || series.length > 1,
          bottom: 0,
          icon: "roundRect",
          itemWidth: 12,
          itemHeight: 8,
          textStyle: { fontSize: 12 },
        },
        radar: {
          indicator: indicators.map((ind) => ({
            name: ind.name,
            max: ind.max,
          })),
          shape,
          splitNumber,
          axisName: {
            show: showLabels,
            fontSize: 11,
            color: "var(--text-secondary, #666)",
          },
          splitArea: {
            show: true,
            areaStyle: {
              color: ["rgba(0,0,0,0.02)", "rgba(0,0,0,0.04)"],
            },
          },
          splitLine: {
            lineStyle: { color: "rgba(0,0,0,0.1)" },
          },
          axisLine: {
            lineStyle: { color: "rgba(0,0,0,0.1)" },
          },
        },
        series: [
          {
            type: "radar" as const,
            data: radarData,
            emphasis: {
              lineStyle: { width: 3 },
            },
          },
        ],
        aria: {
          enabled: true,
          label: {
            description: title
              ? `Radar chart: ${escapeHtml(title)}`
              : "Radar chart",
          },
        },
      } as EChartsOption;
    }, [
      indicators, series, shape, showArea, showLabels, showLegend,
      splitNumber, title, animate, isEmpty, fmt,
    ]);

    const handleClick = useCallback(
      (params: unknown) => {
        if (!onDataPointClick) return;
        onDataPointClick(params);
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
          aria-label={title ?? "Radar chart -- no data"}
          data-testid="radar-chart-empty"
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
            ? `Radar chart: ${escapeHtml(title)}`
            : "Radar chart"
        }
        data-testid="radar-chart"
        {...rest}
      />
    );
  },
);

RadarChart.displayName = "RadarChart";

export default RadarChart;
