/**
 * Tests for chart locale configuration (utils/locale.ts)
 */
import { describe, it, expect, beforeEach } from 'vitest';
import {
  DEFAULT_LOCALE,
  DEFAULT_TIMEZONE,
  DEFAULT_CURRENCY,
  DEFAULT_CURRENCY_SYMBOL,
  getChartLocale,
  setChartLocale,
  useChartLocale,
} from '../utils/locale';

beforeEach(() => {
  // Reset to defaults
  setChartLocale({
    locale: 'tr-TR',
    timezone: 'Europe/Istanbul',
    currency: 'TRY',
    currencySymbol: '₺',
    decimalSeparator: ',',
    thousandsSeparator: '.',
    dateFormat: 'dd.MM.yyyy',
  });
});

describe('locale defaults', () => {
  it('has correct default locale', () => {
    expect(DEFAULT_LOCALE).toBe('tr-TR');
  });

  it('has correct default timezone', () => {
    expect(DEFAULT_TIMEZONE).toBe('Europe/Istanbul');
  });

  it('has correct default currency', () => {
    expect(DEFAULT_CURRENCY).toBe('TRY');
    expect(DEFAULT_CURRENCY_SYMBOL).toBe('₺');
  });
});

describe('getChartLocale', () => {
  it('returns default config', () => {
    const config = getChartLocale();
    expect(config.locale).toBe('tr-TR');
    expect(config.timezone).toBe('Europe/Istanbul');
    expect(config.currency).toBe('TRY');
    expect(config.decimalSeparator).toBe(',');
    expect(config.thousandsSeparator).toBe('.');
  });
});

describe('setChartLocale', () => {
  it('overrides specific fields', () => {
    setChartLocale({ locale: 'en-US', currencySymbol: '$' });
    const config = getChartLocale();
    expect(config.locale).toBe('en-US');
    expect(config.currencySymbol).toBe('$');
    // Others should keep defaults
    expect(config.timezone).toBe('Europe/Istanbul');
  });

  it('merges with defaults', () => {
    setChartLocale({ currency: 'USD' });
    const config = getChartLocale();
    expect(config.currency).toBe('USD');
    expect(config.locale).toBe('tr-TR'); // unchanged
  });
});

describe('useChartLocale', () => {
  it('returns current config (same as getChartLocale)', () => {
    const config = useChartLocale();
    expect(config).toEqual(getChartLocale());
  });

  it('reflects setChartLocale changes', () => {
    setChartLocale({ locale: 'de-DE' });
    const config = useChartLocale();
    expect(config.locale).toBe('de-DE');
  });
});
