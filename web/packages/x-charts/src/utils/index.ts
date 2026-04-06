/* Cross-cutting chart utilities — barrel export */

export {
  formatCompact,
  formatNumber,
  formatCurrency,
  formatPercent,
  useChartFormatter,
} from './formatters';
export type { ChartFormatterOptions } from './formatters';

export {
  sanitizeNumber,
  clampValue,
  sanitizeDataPoints,
  sanitizeSeries,
  sanitizeNumbers,
  validateDataPoints,
  validateSeries,
} from './data-validation';
export type { ValidationResult } from './data-validation';

export {
  DEFAULT_LOCALE,
  DEFAULT_TIMEZONE,
  DEFAULT_CURRENCY,
  DEFAULT_CURRENCY_SYMBOL,
  getChartLocale,
  setChartLocale,
  useChartLocale,
} from './locale';
export type { ChartLocaleConfig } from './locale';
