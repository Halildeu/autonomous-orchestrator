/**
 * FunnelChart -- ECharts-powered funnel chart
 *
 * Renders a funnel/pyramid visualization with optional conversion rate
 * display between stages. Supports vertical/horizontal orientation,
 * configurable label positioning, and sort order.
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
import { sanitizeDataPoints } from "./utils/data-validation";
import type { EChartsOption } from "./renderers/echarts-imports";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface FunnelDataPoint {
  /** Stage name displayed in labels and tooltip. */
  name: string;
  /** Numeric value determining the width of the stage. */
  value: number;
  /** Optional per-stage color override. */
  color?: string;
}

export interface FunnelChartProps {
  /** Data points to render as funnel stages. */
  data: FunnelDataPoint[];
  /** Visual size variant. @default "md" */
  size?: "sm" | "md" | "lg";
  /** Chart title. */
  title?: string;
  /** Sort order for funnel stages. @default "descending" */
  sort?: "descending" | "ascending" | "none";
  /** Pixel gap between funnel stages. @default 2 */
  gap?: number;
  /** Show labels on stages. @default true */
  showLabels?: boolean;
  /** Label placement. @default "inside" */
  labelPosition?: "inside" | "outside" | "left" | "right";
  /** Show conversion percentage between consecutive stages. @default false */
  showConversion?: boolean;
  /** Funnel layout direction. @default "vertical" */
  orientation?: "vertical" | "horizontal";
  /** Horizontal alignment of the funnel shape. @default "center" */
  funnelAlign?: "left" | "center" | "right";
  /** Show legend below the chart. @default false */
  showLegend?: boolean;
  /** Custom value formatter for labels and tooltip. */
  valueFormatter?: (v: number) => string;
  /** Animate on mount. @default true */
  animate?: boolean;
  /** Callback fired when a stage is clicked. */
  onDataPointClick?: (params: unknown) => void;
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
 * Build a conversion-rate map keyed by stage name.
 * The first stage (by sort order) is 100 %; subsequent stages show
 * the percentage relative to their immediate predecessor.
 */
function buildConversionMap(
  data: FunnelDataPoint[],
  sort: string,
): Map<string, number> {
  const sorted = [...data];
  if (sort === "descending") sorted.sort((a, b) => b.value - a.value);
  else if (sort === "ascending") sorted.sort((a, b) => a.value - b.value);
  // "none" keeps the original insertion order

  const map = new Map<string, number>();
  for (let i = 0; i < sorted.length; i++) {
    if (i === 0) {
      map.set(sorted[i].name, 100);
    } else {
      const prev = sorted[i - 1].value;
      const pct = prev !== 0 ? (sorted[i].value / prev) * 100 : 0;
      map.set(sorted[i].name, pct);
    }
  }
  return map;
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export const FunnelChart = React.forwardRef<HTMLDivElement, FunnelChartProps>(
  function FunnelChart(
    {
      data,
      size = "md",
      title,
      sort = "descending",
      gap = 2,
      showLabels = true,
      labelPosition = "inside",
      showConversion = false,
      orientation = "vertical",
      funnelAlign = "center",
      showLegend = false,
      valueFormatter,
      animate = true,
      onDataPointClick,
      className,
      ...rest
    },
    forwardedRef,
  ) {
    const height = SIZE_HEIGHT[size];
    const isEmpty = !data || data.length === 0;
    const safeData = useMemo(
      () => sanitizeDataPoints(data as never) as unknown as FunnelDataPoint[],
      [data],
    );
    const fmt = valueFormatter ?? formatCompact;

    const theme = useMemo(() => buildDesignLabEChartsTheme(), []);

    const option = useMemo((): EChartsOption | null => {
      if (isEmpty) return null;

      const conversionMap = showConversion ? buildConversionMap(safeData, sort) : null;

      /* -- Prepare series data with per-stage colors -- */
      const seriesData = safeData.map((d, i) => ({
        name: d.name,
        value: d.value,
        itemStyle: {
          color: d.color ?? DEFAULT_PALETTE[i % DEFAULT_PALETTE.length],
        },
      }));

      /* -- Label formatter: optionally appends conversion % -- */
      const labelFormatter = (params: { name: string; value: number }) => {
        const base = `${params.name}: ${fmt(params.value)}`;
        if (!conversionMap) return base;
        const pct = conversionMap.get(params.name);
        if (pct === undefined || pct === 100) return base;
        return `${base}\n(${pct.toFixed(1)}%)`;
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
          formatter: (params: unknown) => {
            const p = params as { name: string; value: number; percent: number };
            let tip = `<b>${escapeHtml(p.name)}</b><br/>${fmt(p.value)}`;
            if (conversionMap) {
              const pct = conversionMap.get(p.name);
              if (pct !== undefined && pct !== 100) {
                tip += `<br/>Conversion: ${pct.toFixed(1)}%`;
              }
            }
            return tip;
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
            type: "funnel" as const,
            left: "10%",
            top: title ? 48 : 24,
            bottom: showLegend ? 48 : 24,
            width: "80%",
            sort: sort === "none" ? ("none" as const) : sort,
            orient: orientation === "horizontal" ? "horizontal" : "vertical",
            funnelAlign,
            gap,
            data: seriesData,
            label: showLabels
              ? {
                  show: true,
                  position: labelPosition,
                  formatter: labelFormatter,
                  fontSize: 12,
                }
              : { show: false },
            emphasis: {
              label: {
                show: true,
                fontSize: 14,
                fontWeight: "bold" as const,
              },
            },
            itemStyle: {
              borderColor: "var(--bg-surface, #ffffff)",
              borderWidth: 1,
            },
            cursor: onDataPointClick ? "pointer" : "default",
          },
        ],
        aria: {
          enabled: true,
          label: {
            description: title
              ? `Funnel chart: ${escapeHtml(title)}`
              : "Funnel chart",
          },
        },
      } as EChartsOption;
    }, [
      safeData, size, title, sort, gap, showLabels, labelPosition,
      showConversion, orientation, funnelAlign, showLegend,
      fmt, animate, onDataPointClick, isEmpty,
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
          aria-label={title ?? "Funnel chart -- no data"}
          data-testid="funnel-chart-empty"
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
            ? `Funnel chart: ${escapeHtml(title)}`
            : "Funnel chart"
        }
        data-testid="funnel-chart"
        {...rest}
      />
    );
  },
);

FunnelChart.displayName = "FunnelChart";

export default FunnelChart;
