/* ------------------------------------------------------------------ */
/*  @mfe/x-charts — Barrel export                                     */
/*  ALL chart components owned by x-charts (ECharts engine)            */
/* ------------------------------------------------------------------ */

/* Core charts (ECharts native — P1) */
export { BarChart } from "./BarChart";
export type { BarChartProps } from "./BarChart";
export { LineChart } from "./LineChart";
export type { LineChartProps } from "./LineChart";
export { AreaChart } from "./AreaChart";
export type { AreaChartProps } from "./AreaChart";
export { PieChart } from "./PieChart";
export type { PieChartProps } from "./PieChart";
export { ScatterChart } from "./ScatterChart";
export type { ScatterChartProps } from "./ScatterChart";

/* Enterprise charts (ECharts native — P3-A) */
export { RadarChart } from "./RadarChart";
export type { RadarChartProps } from "./RadarChart";
export { TreemapChart } from "./TreemapChart";
export type { TreemapChartProps } from "./TreemapChart";
export { HeatmapChart } from "./HeatmapChart";
export type { HeatmapChartProps } from "./HeatmapChart";
export { GaugeChart } from "./GaugeChart";
export type { GaugeChartProps } from "./GaugeChart";
export { WaterfallChart } from "./WaterfallChart";
export type { WaterfallChartProps } from "./WaterfallChart";
export { FunnelChart } from "./FunnelChart";
export type { FunnelChartProps } from "./FunnelChart";
export { SankeyChart } from "./SankeyChart";
export type { SankeyChartProps } from "./SankeyChart";
export { SunburstChart } from "./SunburstChart";
export type { SunburstChartProps } from "./SunburstChart";

/* Composition */
export { ChartContainer } from "./ChartContainer";
export type { ChartContainerProps } from "./ChartContainer";
export { ChartDashboard } from "./ChartDashboard";
export type { ChartDashboardProps, ChartDashboardItemProps } from "./ChartDashboard";
export { SparklineChart } from "./SparklineChart";
export type { SparklineChartProps } from "./SparklineChart";
export { MiniChart } from "./MiniChart";
export type { MiniChartProps, MiniChartDataPoint } from "./MiniChart";
export { KPICard } from "./KPICard";
export type { KPICardProps, KPICardTrend } from "./KPICard";
export { StatWidget } from "./StatWidget";
export type { StatWidgetProps } from "./StatWidget";
export { ChartLegend } from "./ChartLegend";
export type { ChartLegendProps, ChartLegendItem } from "./ChartLegend";

/* Interactions */
export { useChartInteractions } from "./useChartInteractions";
export type { ChartInteractionState, ChartInteractionOptions, ChartInteractionHandlers } from "./useChartInteractions";
export { ChartToolbar } from "./ChartToolbar";
export type { ChartToolbarProps } from "./ChartToolbar";
export { useChartResize } from "./useChartResize";
export type { ChartResizeState, UseChartResizeOptions } from "./useChartResize";
export { useRealTimeData } from "./useRealTimeData";
export type { RealTimeDataOptions, RealTimeDataState } from "./useRealTimeData";
export { useDashboardComposition } from "./composition/useDashboardComposition";
export type { DateRange, UseDashboardCompositionOptions, UseDashboardCompositionReturn } from "./composition/useDashboardComposition";
export { useChartVariants } from "./useChartVariants";
export type { ChartConfig, ChartVariant, UseChartVariantsReturn } from "./useChartVariants";
export { useResponsiveBreakpoint, useResponsiveChartConfig } from "./useResponsiveChart";
export type { Breakpoint, ResponsiveChartConfig } from "./useResponsiveChart";

/* ------------------------------------------------------------------ */
/*  ECharts Foundation (P1)                                           */
/* ------------------------------------------------------------------ */

export { registerECharts, echarts } from "./renderers/echarts-imports";
export { useEChartsRenderer } from "./renderers/echarts-renderer";
export type { EChartsRendererOptions, EChartsRendererState } from "./renderers/echarts-renderer";
export { chartSpecToEChartsOption } from "./spec/chartSpecToEChartsOption";
export { validateChartSpec } from "./spec/validateChartSpec";
export type { ChartSpec, ChartType, ChartChannel, ChartEncoding } from "./spec/ChartSpec";

/* Theme (P1 + P3-B) */
export { buildDesignLabEChartsTheme } from "./theme/DesignLabEChartsTheme";
export type { DesignLabThemeOptions } from "./theme/DesignLabEChartsTheme";
export { buildDesignLabEChartsDarkTheme, isDarkMode } from "./theme/DesignLabEChartsDarkTheme";
export { buildDesignLabEChartsHighContrastTheme } from "./theme/DesignLabEChartsHighContrastTheme";
export { buildDesignLabEChartsPrintTheme } from "./theme/DesignLabEChartsPrintTheme";
export { COLORBLIND_PALETTES } from "./theme/colorblind-palettes";
export { DECAL_PATTERNS } from "./theme/decal-patterns";

/* Security */
export { sanitizeChartText, sanitizeChartData, validateStreamUrl } from "./security/sanitizeChartText";

/* A11y */
export { ChartKeyboardNav } from "./a11y/ChartKeyboardNav";
export type { ChartKeyboardNavProps } from "./a11y/ChartKeyboardNav";
export { ChartDataTable } from "./a11y/ChartDataTable";
export type { ChartDataTableProps, ChartDataTableColumn } from "./a11y/ChartDataTable";
export { ChartAriaLive } from "./a11y/ChartAriaLive";
export type { ChartAriaLiveProps } from "./a11y/ChartAriaLive";
export { useReducedMotion } from "./a11y/useReducedMotion";

/* States */
export { ChartLoadingState } from "./states/ChartLoadingState";
export type { ChartLoadingStateProps } from "./states/ChartLoadingState";
export { ChartEmptyState } from "./states/ChartEmptyState";
export type { ChartEmptyStateProps } from "./states/ChartEmptyState";
export { ChartErrorState } from "./states/ChartErrorState";
export type { ChartErrorStateProps } from "./states/ChartErrorState";
export { ChartErrorBoundary } from "./states/ChartErrorBoundary";
export type { ChartErrorBoundaryProps } from "./states/ChartErrorBoundary";

/* ------------------------------------------------------------------ */
/*  Cross-Filter Bus (P2)                                             */
/* ------------------------------------------------------------------ */

export { CrossFilterChart } from "./cross-filter/CrossFilterChart";
export type { CrossFilterChartProps } from "./cross-filter/CrossFilterChart";
export { createCrossFilterStore } from "./cross-filter/createCrossFilterStore";
export { CrossFilterProvider, useCrossFilter, useCrossFilterStoreApi } from "./cross-filter/useCrossFilterStore";
export { useChartCrossFilter } from "./cross-filter/useChartCrossFilter";
export { useGridCrossFilter } from "./cross-filter/useGridCrossFilter";
export { createEventBridge } from "./cross-filter/eventBridge";
export { filtersByGroup, filtersForChart, activeFilterCount, canUndo, canRedo } from "./cross-filter/selectors";
export { useQueryCancellation } from "./cross-filter/useQueryCancellation";
export type { CrossFilterEntry, DrillLevel, HistoryEntry } from "./cross-filter/types";
export { useDrillDown } from "./drill-down/useDrillDown";
export { DrillDownBreadcrumb } from "./drill-down/DrillDownBreadcrumb";
export { useChartAnimation } from "./animation/useChartAnimation";
export { useTouchGestures } from "./touch/useTouchGestures";
export { MobileTooltip } from "./touch/MobileTooltip";
export { DataVolumeIndicator } from "./components/DataVolumeIndicator";

/* ------------------------------------------------------------------ */
/*  i18n + RTL (P3-C)                                                 */
/* ------------------------------------------------------------------ */

export { registerEChartsLocale, getEChartsLocale, ECHARTS_LOCALE_MAP } from "./i18n/echarts-locale";
export { createNumberFormatter, createDateFormatter } from "./i18n/formatters";
export { isRTL, isRTLLocale, applyRTLTransforms } from "./i18n/rtl";

/* Cross-cutting Utils (P3-E) */
export {
  formatCompact, formatNumber, formatCurrency, formatPercent, useChartFormatter,
  sanitizeNumber, clampValue, sanitizeDataPoints, sanitizeSeries, sanitizeNumbers,
  validateDataPoints, validateSeries,
  DEFAULT_LOCALE, DEFAULT_TIMEZONE, DEFAULT_CURRENCY, DEFAULT_CURRENCY_SYMBOL,
  getChartLocale, setChartLocale, useChartLocale,
} from "./utils";
export type { ChartFormatterOptions, ValidationResult, ChartLocaleConfig } from "./utils";

/* Data Transforms (P3-C) */
export { movingAverage, percentile, standardDeviation, linearRegression } from "./transforms/statistical";

/* Responsive (P3-D) */
export { useAutoGranularity, resolveGranularity } from "./responsive/useAutoGranularity";
export { useResponsiveLegend } from "./responsive/useResponsiveLegend";
export { useResponsiveChartType } from "./responsive/useResponsiveChartType";

/* ------------------------------------------------------------------ */
/*  AI Integration (P5)                                                */
/* ------------------------------------------------------------------ */

export { nlToChartSpec } from "./ai/nl-to-chart-spec";
export type { NLToChartSpecOptions, NLToChartSpecResult } from "./ai/nl-to-chart-spec";
export { detectAnomalies, identifyTrends } from "./ai/auto-insight";
export type { Anomaly, Trend, InsightResult } from "./ai/auto-insight";
export { suggestChartType } from "./ai/chart-type-suggestion";
export type { ChartTypeSuggestion, DataShapeAnalysis } from "./ai/chart-type-suggestion";
export { generateChartDescription } from "./ai/chart-description";

/* ------------------------------------------------------------------ */
/*  Grid Adapter (P4)                                                  */
/* ------------------------------------------------------------------ */

export { AGGridAdapter } from "./grid-adapter/AGGridAdapter";
export { useChartGridLink, autoMapColumns } from "./grid-adapter/useChartGridLink";
export type {
  GridAdapter, GridColumnDef, GridFilterEntry, GridSortEntry,
  GridSelectionEvent, ChartGridLinkConfig, ColumnChartMapping,
} from "./grid-adapter/types";
export type { AGGridApi } from "./grid-adapter/AGGridAdapter";
export type { ChartGridLinkState } from "./grid-adapter/useChartGridLink";

/* ------------------------------------------------------------------ */
/*  Advanced Analytics (P8)                                            */
/* ------------------------------------------------------------------ */

export { chartPluginRegistry, registerChartPlugin } from "./advanced/plugin-registry";
export type { ChartPlugin, ChartPluginConfig } from "./advanced/plugin-registry";
export { renderDashboardFromConfig } from "./advanced/dashboard-as-code";
export type { DashboardConfig, DashboardWidgetConfig } from "./advanced/dashboard-as-code";
export { useWhatIfAnalysis } from "./advanced/what-if";
export type { WhatIfParameter, WhatIfResult } from "./advanced/what-if";

/* ------------------------------------------------------------------ */
/*  Collaboration & Offline (P7)                                       */
/* ------------------------------------------------------------------ */

export { useDashboardState, serializeState, deserializeState } from "./collaboration/dashboard-state";
export { useChartExport } from "./collaboration/chart-export";
export type { ExportFormat, ExportOptions } from "./collaboration/chart-export";
export { useDashboardSharing, createShareUrl, parseShareUrl } from "./collaboration/dashboard-sharing";
export { useChartAnnotations } from "./collaboration/chart-annotations";
export type { Annotation, AnnotationType } from "./collaboration/chart-annotations";
export { useOfflineCache } from "./collaboration/offline-cache";

/* ------------------------------------------------------------------ */
/*  Performance (P6)                                                   */
/* ------------------------------------------------------------------ */

export { downsampleLTTB } from "./performance/lttb";
export { createWorkerBridge } from "./performance/worker-bridge";
export type { WorkerBridge, WorkerTask } from "./performance/worker-bridge";
export { useProgressiveRender } from "./performance/progressive-render";
export { useLazyChart } from "./performance/lazy-chart";
export { LRUCache } from "./performance/lru-cache";
export { lazyChartImport } from "./performance/code-split";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export type { ChartSize, ChartDataPoint, ChartSeries, ChartClickEvent, ChartLocaleText } from "./types";
