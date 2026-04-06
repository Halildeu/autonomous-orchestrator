/**
 * Chart Formatters — Cross-cutting value formatting
 *
 * Wraps i18n/formatters.ts and adds chart-specific convenience functions.
 * All 13 charts use these as default valueFormatter / tooltip formatter.
 *
 * Locale rules (tr-TR):
 *  - Compact: 205M, 67K, 1.2B
 *  - Currency: ₺67.058 (full) or ₺67K (compact)
 *  - Decimal separator: , (virgül)
 *  - Thousands separator: . (nokta)
 *  - Percent: %15,8
 */

import { createNumberFormatter } from '../i18n/formatters';
import { getChartLocale } from './locale';

/* ------------------------------------------------------------------ */
/*  Compact formatter (205M, 67K, 1.2B)                                */
/* ------------------------------------------------------------------ */

const COMPACT_THRESHOLDS: [number, string, number][] = [
  [1_000_000_000, 'B', 1_000_000_000],
  [1_000_000, 'M', 1_000_000],
  [10_000, 'K', 1_000],
];

/**
 * Format a number in compact notation.
 * 204988664 → "205M", 67058 → "67.1K", 1200000000 → "1.2B"
 * Values < 10,000 are formatted with thousands separators.
 */
export function formatCompact(value: number): string {
  if (value == null || isNaN(value)) return '–';
  const abs = Math.abs(value);
  const sign = value < 0 ? '-' : '';

  for (const [threshold, suffix, divisor] of COMPACT_THRESHOLDS) {
    if (abs >= threshold) {
      const divided = abs / divisor;
      // Use at most 1 decimal, drop trailing .0
      const formatted = divided >= 100
        ? Math.round(divided).toString()
        : divided.toFixed(1).replace(/\.0$/, '');
      return `${sign}${formatted}${suffix}`;
    }
  }

  // Below 10K — use locale thousands separator
  const locale = getChartLocale();
  const fmt = createNumberFormatter({
    locale: locale.locale,
    maximumFractionDigits: abs % 1 === 0 ? 0 : 1,
  });
  return fmt(value);
}

/* ------------------------------------------------------------------ */
/*  Number formatter (1.234.567,89)                                    */
/* ------------------------------------------------------------------ */

/**
 * Format a number with locale-aware thousands and decimal separators.
 * 1234567.89 → "1.234.567,89" (tr-TR)
 */
export function formatNumber(value: number, fractionDigits?: number): string {
  if (value == null || isNaN(value)) return '–';
  const locale = getChartLocale();
  const fmt = createNumberFormatter({
    locale: locale.locale,
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits ?? 2,
  });
  return fmt(value);
}

/* ------------------------------------------------------------------ */
/*  Currency formatter (₺67.058 or ₺67K)                               */
/* ------------------------------------------------------------------ */

/**
 * Format as currency. Compact mode for large values.
 * 67058 → "₺67.058" (full) or "₺67,1K" (compact)
 */
export function formatCurrency(value: number, compact = false): string {
  if (value == null || isNaN(value)) return '–';
  const locale = getChartLocale();

  if (compact) {
    return `${locale.currencySymbol}${formatCompact(value)}`;
  }

  const fmt = createNumberFormatter({
    locale: locale.locale,
    style: 'currency',
    currency: locale.currency,
    maximumFractionDigits: 0,
  });
  return fmt(value);
}

/* ------------------------------------------------------------------ */
/*  Percent formatter (%15,8)                                          */
/* ------------------------------------------------------------------ */

/**
 * Format a decimal as percent. 0.158 → "%15,8"
 */
export function formatPercent(value: number): string {
  if (value == null || isNaN(value)) return '–';
  const locale = getChartLocale();
  const fmt = createNumberFormatter({
    locale: locale.locale,
    style: 'percent',
    minimumFractionDigits: 0,
    maximumFractionDigits: 1,
  });
  return fmt(value);
}

/* ------------------------------------------------------------------ */
/*  React hook — useChartFormatter                                     */
/* ------------------------------------------------------------------ */

export interface ChartFormatterOptions {
  style?: 'compact' | 'number' | 'currency' | 'percent';
  compactCurrency?: boolean;
  fractionDigits?: number;
}

/**
 * React hook that returns a formatter function.
 * Default style is 'compact'.
 */
export function useChartFormatter(options?: ChartFormatterOptions): (value: number) => string {
  const style = options?.style ?? 'compact';

  switch (style) {
    case 'currency':
      return (v: number) => formatCurrency(v, options?.compactCurrency);
    case 'percent':
      return formatPercent;
    case 'number':
      return (v: number) => formatNumber(v, options?.fractionDigits);
    case 'compact':
    default:
      return formatCompact;
  }
}
