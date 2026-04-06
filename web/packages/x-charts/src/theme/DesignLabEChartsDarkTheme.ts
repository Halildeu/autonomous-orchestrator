/**
 * DesignLabEChartsDarkTheme — Dark Mode ECharts Theme Adapter
 *
 * Detects dark mode via:
 *   1. Explicit `dark` option
 *   2. `[data-theme="dark"]` attribute on <html>
 *   3. CSS `prefers-color-scheme: dark` media query
 *
 * Reads CSS custom properties scoped to dark mode. Falls back to
 * hardcoded dark tokens matching the design-lab dark preset.
 *
 * @see decisions/topics/chart-viz-engine-selection.v1.json (D-009)
 * @see DesignLabEChartsTheme.ts (light theme — same structure)
 */

import type { ColorblindPalette } from '../spec/ChartSpec';
import { COLORBLIND_PALETTES } from './colorblind-palettes';

/* ------------------------------------------------------------------ */
/*  Dark Mode Detection                                                */
/* ------------------------------------------------------------------ */

/**
 * Detect whether the current environment is in dark mode.
 * Priority: data-theme attribute > prefers-color-scheme media query.
 */
export function isDarkMode(): boolean {
  if (typeof document === 'undefined') return false;
  const attr = document.documentElement.getAttribute('data-theme');
  if (attr === 'dark') return true;
  if (attr === 'light') return false;
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches;
}

/* ------------------------------------------------------------------ */
/*  CSS Variable Reader (with dark fallbacks)                          */
/* ------------------------------------------------------------------ */

const getCSSVar = (varName: string, fallback: string): string => {
  if (typeof document === 'undefined') return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
  return value || fallback;
};

/* ------------------------------------------------------------------ */
/*  Dark Theme Builder                                                 */
/* ------------------------------------------------------------------ */

export interface DarkThemeOptions {
  /** Colorblind-safe palette selection. @default 'default' */
  colorblindPalette?: ColorblindPalette;
  /** Override font family. */
  fontFamily?: string;
}

/**
 * Build an ECharts dark theme from Design Lab dark-mode CSS custom properties.
 *
 * Usage:
 * ```ts
 * const theme = buildDesignLabEChartsDarkTheme();
 * echarts.registerTheme('design-lab-dark', theme);
 * ```
 */
export function buildDesignLabEChartsDarkTheme(options?: DarkThemeOptions): Record<string, unknown> {
  const {
    colorblindPalette = 'default',
    fontFamily: fontFamilyOverride,
  } = options ?? {};

  // Dark mode tokens (design-lab dark preset fallbacks)
  const fontFamily = fontFamilyOverride ?? getCSSVar('--font-family-sans', 'Inter, system-ui, sans-serif');
  const textPrimary = getCSSVar('--text-primary', '#e5e7eb');
  const textSecondary = getCSSVar('--text-secondary', '#9ca3af');
  const textTertiary = getCSSVar('--text-tertiary', '#6b7280');
  const bgSurface = getCSSVar('--bg-surface', '#1f2937');
  const bgMuted = getCSSVar('--bg-muted', '#111827');
  const borderDefault = getCSSVar('--border-default', '#374151');
  const _actionPrimary = getCSSVar('--action-primary', '#60a5fa');

  // Brighter palette for dark backgrounds
  const palette = colorblindPalette === 'default'
    ? [
        getCSSVar('--action-primary', '#60a5fa'),
        getCSSVar('--state-success-text', '#4ade80'),
        getCSSVar('--state-warning-text', '#fbbf24'),
        getCSSVar('--state-error-text', '#f87171'),
        getCSSVar('--state-info-text', '#22d3ee'),
        getCSSVar('--action-secondary', '#a78bfa'),
        '#f472b6', '#2dd4bf', '#fb923c', '#818cf8',
      ]
    : COLORBLIND_PALETTES[colorblindPalette] ?? COLORBLIND_PALETTES.deuteranopia;

  return {
    color: palette,
    backgroundColor: 'transparent',
    textStyle: {
      fontFamily,
      color: textPrimary,
    },
    title: {
      textStyle: {
        fontFamily,
        color: textPrimary,
        fontSize: 16,
        fontWeight: 600,
      },
      subtextStyle: {
        fontFamily,
        color: textSecondary,
        fontSize: 13,
      },
      padding: [0, 0, 12, 0],
    },
    legend: {
      textStyle: {
        fontFamily,
        color: textPrimary,
        fontSize: 12,
      },
      pageTextStyle: { color: textSecondary },
      icon: 'roundRect',
      itemWidth: 12,
      itemHeight: 12,
      itemGap: 16,
    },
    tooltip: {
      backgroundColor: bgSurface,
      borderColor: borderDefault,
      borderWidth: 1,
      textStyle: {
        fontFamily,
        color: textPrimary,
        fontSize: 13,
      },
      extraCssText: 'box-shadow: 0 4px 12px rgba(0,0,0,0.32); border-radius: 8px; padding: 10px 14px;',
    },
    categoryAxis: {
      axisLine: { lineStyle: { color: borderDefault } },
      axisTick: { lineStyle: { color: borderDefault } },
      axisLabel: { color: textSecondary, fontFamily, fontSize: 11 },
      splitLine: { lineStyle: { color: borderDefault, type: 'dashed', opacity: 0.3 } },
      nameTextStyle: { color: textTertiary, fontFamily, fontSize: 11 },
    },
    valueAxis: {
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: textSecondary, fontFamily, fontSize: 11 },
      splitLine: { lineStyle: { color: borderDefault, type: 'dashed', opacity: 0.3 } },
      nameTextStyle: { color: textTertiary, fontFamily, fontSize: 11 },
    },
    bar: {
      itemStyle: { borderRadius: [4, 4, 0, 0] },
      barMaxWidth: 40,
    },
    line: {
      symbolSize: 6,
      symbol: 'circle',
      lineStyle: { width: 2 },
      smooth: false,
    },
    pie: {
      itemStyle: { borderColor: bgMuted, borderWidth: 2 },
      label: { fontFamily, color: textPrimary, fontSize: 12 },
    },
    scatter: {
      symbolSize: 8,
    },
    gauge: {
      axisLine: { lineStyle: { color: [[1, borderDefault]] } },
      axisTick: { lineStyle: { color: textTertiary } },
      axisLabel: { color: textSecondary },
      detail: { color: textPrimary },
    },
    radar: {
      axisLine: { lineStyle: { color: borderDefault } },
      splitLine: { lineStyle: { color: borderDefault, opacity: 0.3 } },
      splitArea: { areaStyle: { color: ['transparent', 'rgba(255,255,255,0.02)'] } },
      axisName: { color: textSecondary },
    },
    // Animation defaults
    animationDuration: 500,
    animationEasing: 'cubicOut',
    animationDurationUpdate: 300,
  };
}
