/**
 * WaterfallChart -- ECharts-powered waterfall chart
 *
 * Implements the waterfall pattern using stacked bars: an invisible "base"
 * series holds the running total offset, and a visible "value" series
 * renders each segment colored by type (increase / decrease / total).
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

export type WaterfallItemType = "increase" | "decrease" | "total";

export interface WaterfallDataPoint {
  /** Category label displayed on the axis. */
  label: string;
  /** Numeric value. Positive = increase, negative = decrease. */
  value: number;
  /** Explicit type override. Auto-detected when omitted. */
  type?: WaterfallItemType;
}

export interface WaterfallChartProps {
  /** Data points to render as waterfall bars. */
  data: WaterfallDataPoint[];
  /** Visual size variant. @default "md" */
  size?: "sm" | "md" | "lg";
  /** Chart title. */
  title?: string;
  /** Colors per waterfall segment type. */
  colors?: {
    increase?: string;
    decrease?: string;
    total?: string;
  };
  /** Draw dashed connector lines between adjacent bars. @default true */
  showConnector?: boolean;
  /** Show value labels on bars. @default true */
  showValues?: boolean;
  /** Custom value formatter for labels and tooltip. */
  valueFormatter?: (v: number) => string;
  /** Bar orientation. @default "vertical" */
  orientation?: "vertical" | "horizontal";
  /** Show legend below the chart. @default false */
  showLegend?: boolean;
  /** Animate bars on mount. @default true */
  animate?: boolean;
  /** Callback fired when a bar is clicked. */
  onDataPointClick?: (params: unknown) => void;
  /** Additional class name. */
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const SIZE_HEIGHT: Record<"sm" | "md" | "lg", number> = { sm: 200, md: 300, lg: 400 };

const DEFAULT_COLORS = {
  increase: "#22c55e",
  decrease: "#ef4444",
  total: "#3b82f6",
};

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const escapeHtml = (t: string): string =>
  t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/**
 * Resolve explicit or auto-detected type for each data point.
 * Last item defaults to "total"; positive values default to "increase";
 * negative values default to "decrease".
 */
function resolveType(item: WaterfallDataPoint, index: number, total: number): WaterfallItemType {
  if (item.type) return item.type;
  if (index === total - 1) return "total";
  return item.value >= 0 ? "increase" : "decrease";
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

export const WaterfallChart = React.forwardRef<HTMLDivElement, WaterfallChartProps>(
  function WaterfallChart(
    {
      data,
      size = "md",
      title,
      colors: colorsProp,
      showConnector = true,
      showValues = true,
      valueFormatter,
      orientation = "vertical",
      showLegend = false,
      animate = true,
      onDataPointClick,
      className,
      ...rest
    },
    forwardedRef,
  ) {
    const height = SIZE_HEIGHT[size];
    const isEmpty = !data || data.length === 0;
    const isHorizontal = orientation === "horizontal";
    const safeData = useMemo(
      () => sanitizeDataPoints(data as never) as unknown as WaterfallDataPoint[],
      [data],
    );
    const fmt = valueFormatter ?? formatCompact;

    const palette = useMemo(
      () => ({
        increase: colorsProp?.increase ?? DEFAULT_COLORS.increase,
        decrease: colorsProp?.decrease ?? DEFAULT_COLORS.decrease,
        total: colorsProp?.total ?? DEFAULT_COLORS.total,
      }),
      [colorsProp],
    );

    const theme = useMemo(() => buildDesignLabEChartsTheme(), []);

    const option = useMemo((): EChartsOption | null => {
      if (isEmpty) return null;

      const len = safeData.length;
      const types = safeData.map((d, i) => resolveType(d, i, len));

      /* -- Running total & base offset calculation -- */
      const baseValues: number[] = [];
      const displayValues: number[] = [];
      let runningTotal = 0;

      for (let i = 0; i < len; i++) {
        const t = types[i];
        if (t === "total") {
          baseValues.push(0);
          displayValues.push(runningTotal);
        } else {
          const val = safeData[i].value;
          if (val >= 0) {
            baseValues.push(runningTotal);
            displayValues.push(val);
            runningTotal += val;
          } else {
            runningTotal += val;
            baseValues.push(runningTotal);
            displayValues.push(Math.abs(val));
          }
        }
      }

      const labels = safeData.map((d) => d.label);
      const barColors = types.map((t) => palette[t]);

      /* -- Connector markLines between adjacent bars -- */
      const markLineData: Array<Record<string, unknown>[]> = [];
      if (showConnector) {
        for (let i = 0; i < len - 1; i++) {
          const topValue = baseValues[i] + displayValues[i];
          const coord = isHorizontal
            ? [{ yAxis: i, xAxis: topValue }, { yAxis: i + 1, xAxis: topValue }]
            : [{ xAxis: i, yAxis: topValue }, { xAxis: i + 1, yAxis: topValue }];
          markLineData.push(coord as Array<Record<string, unknown>>);
        }
      }

      const categoryAxis = {
        type: "category" as const,
        data: labels,
        axisLabel: { fontSize: 11 },
        axisTick: { alignWithLabel: true },
      };

      const valueAxis = {
        type: "value" as const,
        axisLabel: {
          fontSize: 11,
          formatter: (v: number) => fmt(v),
        },
        splitLine: { show: true, lineStyle: { type: "dashed" as const } },
      };

      /* -- Invisible base series (stacked underneath) -- */
      const baseSeries = {
        type: "bar" as const,
        name: "__waterfall_base__",
        stack: "waterfall",
        data: baseValues,
        itemStyle: { color: "transparent" },
        emphasis: { itemStyle: { color: "transparent" } },
        tooltip: { show: false },
        cursor: "default" as const,
      };

      /* -- Visible value series -- */
      // Capture final running total for "total" type label display
      const finalRunningTotal = runningTotal;
      const valueSeries = {
        type: "bar" as const,
        name: title ?? "Value",
        stack: "waterfall",
        data: displayValues.map((v, i) => ({
          value: v,
          itemStyle: { color: barColors[i] },
        })),
        label: showValues
          ? {
              show: true,
              position: isHorizontal ? ("right" as const) : ("top" as const),
              formatter: (p: { dataIndex: number }) => {
                const t = types[p.dataIndex];
                const originalVal = safeData[p.dataIndex].value;
                if (t === "total") return fmt(finalRunningTotal);
                return fmt(originalVal);
              },
              fontSize: 11,
            }
          : { show: false },
        markLine:
          showConnector && markLineData.length > 0
            ? {
                symbol: "none",
                lineStyle: { color: "#94a3b8", type: "dashed" as const, width: 1 },
                data: markLineData,
                label: { show: false },
                silent: true,
              }
            : undefined,
        cursor: onDataPointClick ? "pointer" : ("default" as const),
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
          trigger: "axis",
          confine: true,
          axisPointer: { type: "shadow" },
          formatter: (params: unknown) => {
            const list = Array.isArray(params) ? params : [params];
            const visible = list.find(
              (p: Record<string, unknown>) =>
                (p as { seriesName: string }).seriesName !== "__waterfall_base__",
            ) as { dataIndex: number; name: string } | undefined;
            if (!visible) return "";
            const idx = visible.dataIndex;
            const t = types[idx];
            const originalVal = safeData[idx].value;
            const prefix = t === "total" ? "Total: " : t === "increase" ? "+" : "";
            const displayVal = t === "total" ? finalRunningTotal : originalVal;
            return `<b>${escapeHtml(visible.name)}</b><br/>${prefix}${fmt(displayVal)}`;
          },
        },
        legend: {
          show: showLegend,
          bottom: 0,
          icon: "roundRect",
          itemWidth: 12,
          itemHeight: 8,
          textStyle: { fontSize: 12 },
          data: [title ?? "Value"],
        },
        grid: {
          top: title ? 48 : 24,
          right: 16,
          bottom: showLegend ? 48 : 24,
          left: 16,
          containLabel: true,
        },
        xAxis: isHorizontal ? valueAxis : categoryAxis,
        yAxis: isHorizontal ? categoryAxis : valueAxis,
        series: [baseSeries, valueSeries],
        aria: {
          enabled: true,
          label: {
            description: title
              ? `Waterfall chart: ${escapeHtml(title)}`
              : "Waterfall chart",
          },
        },
      } as EChartsOption;
    }, [
      safeData, size, title, palette, showConnector, showValues,
      fmt, orientation, showLegend, animate,
      onDataPointClick, isEmpty, isHorizontal,
    ]);

    const handleClick = useCallback(
      (params: unknown) => {
        if (!onDataPointClick) return;
        const p = params as { seriesName: string };
        if (p.seriesName === "__waterfall_base__") return;
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
          aria-label={title ?? "Waterfall chart -- no data"}
          data-testid="waterfall-chart-empty"
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
            ? `Waterfall chart: ${escapeHtml(title)}`
            : "Waterfall chart"
        }
        data-testid="waterfall-chart"
        {...rest}
      />
    );
  },
);

WaterfallChart.displayName = "WaterfallChart";

export default WaterfallChart;
