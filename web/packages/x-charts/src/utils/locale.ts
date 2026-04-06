/**
 * Chart Locale Defaults & Hook
 *
 * Centralizes locale configuration for all chart components.
 * Default: tr-TR with Turkish number/date formatting conventions.
 */

export const DEFAULT_LOCALE = 'tr-TR';
export const DEFAULT_TIMEZONE = 'Europe/Istanbul';
export const DEFAULT_CURRENCY = 'TRY';
export const DEFAULT_CURRENCY_SYMBOL = '₺';

export interface ChartLocaleConfig {
  locale: string;
  timezone: string;
  currency: string;
  currencySymbol: string;
  decimalSeparator: string;
  thousandsSeparator: string;
  dateFormat: string;
}

const DEFAULT_CONFIG: ChartLocaleConfig = {
  locale: DEFAULT_LOCALE,
  timezone: DEFAULT_TIMEZONE,
  currency: DEFAULT_CURRENCY,
  currencySymbol: DEFAULT_CURRENCY_SYMBOL,
  decimalSeparator: ',',
  thousandsSeparator: '.',
  dateFormat: 'dd.MM.yyyy',
};

let _activeConfig: ChartLocaleConfig = { ...DEFAULT_CONFIG };

/** Set the active chart locale (call once at app init). */
export function setChartLocale(config: Partial<ChartLocaleConfig>): void {
  _activeConfig = { ...DEFAULT_CONFIG, ...config };
}

/** Get the current chart locale config. */
export function getChartLocale(): ChartLocaleConfig {
  return _activeConfig;
}

/** React hook — returns current locale config. */
export function useChartLocale(): ChartLocaleConfig {
  return _activeConfig;
}
