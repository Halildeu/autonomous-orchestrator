/**
 * Tests for cross-cutting chart formatters (utils/formatters.ts)
 */
import { describe, it, expect, beforeEach } from 'vitest';
import {
  formatCompact,
  formatNumber,
  formatCurrency,
  formatPercent,
  useChartFormatter,
} from '../utils/formatters';
import { setChartLocale } from '../utils/locale';

beforeEach(() => {
  // Reset to default tr-TR locale before each test
  setChartLocale({
    locale: 'tr-TR',
    currency: 'TRY',
    currencySymbol: '₺',
    decimalSeparator: ',',
    thousandsSeparator: '.',
  });
});

/* ------------------------------------------------------------------ */
/*  formatCompact                                                      */
/* ------------------------------------------------------------------ */

describe('formatCompact', () => {
  it('formats billions', () => {
    expect(formatCompact(1_200_000_000)).toBe('1.2B');
    expect(formatCompact(5_000_000_000)).toBe('5B');
  });

  it('formats millions', () => {
    expect(formatCompact(204_988_664)).toBe('205M');
    expect(formatCompact(1_500_000)).toBe('1.5M');
    expect(formatCompact(12_300_000)).toBe('12.3M');
  });

  it('formats thousands (>= 10K)', () => {
    expect(formatCompact(67_058)).toBe('67.1K');
    expect(formatCompact(100_000)).toBe('100K');
    expect(formatCompact(10_000)).toBe('10K');
  });

  it('formats small numbers with locale separators', () => {
    const result = formatCompact(1234);
    // tr-TR uses . for thousands
    expect(result).toMatch(/1[.]?234/);
  });

  it('formats zero', () => {
    expect(formatCompact(0)).toBe('0');
  });

  it('handles negative numbers', () => {
    expect(formatCompact(-204_988_664)).toBe('-205M');
    expect(formatCompact(-67_058)).toBe('-67.1K');
  });

  it('handles NaN and null', () => {
    expect(formatCompact(NaN)).toBe('–');
    expect(formatCompact(null as unknown as number)).toBe('–');
    expect(formatCompact(undefined as unknown as number)).toBe('–');
  });

  it('drops trailing .0 from compact values', () => {
    expect(formatCompact(200_000_000)).toBe('200M');
    expect(formatCompact(50_000)).toBe('50K');
  });
});

/* ------------------------------------------------------------------ */
/*  formatNumber                                                       */
/* ------------------------------------------------------------------ */

describe('formatNumber', () => {
  it('formats with tr-TR separators', () => {
    const result = formatNumber(1234567.89);
    // Should use comma for decimal, dot for thousands
    expect(result).toContain(',');
  });

  it('handles custom fraction digits', () => {
    const result = formatNumber(1234.5, 0);
    expect(result).not.toContain(',');
  });

  it('handles NaN', () => {
    expect(formatNumber(NaN)).toBe('–');
  });
});

/* ------------------------------------------------------------------ */
/*  formatCurrency                                                     */
/* ------------------------------------------------------------------ */

describe('formatCurrency', () => {
  it('formats full currency', () => {
    const result = formatCurrency(67058);
    // Should contain TRY currency symbol or formatting
    expect(result).toBeTruthy();
    expect(result).not.toBe('–');
  });

  it('formats compact currency', () => {
    const result = formatCurrency(67058, true);
    expect(result).toContain('₺');
    expect(result).toContain('K');
  });

  it('handles NaN', () => {
    expect(formatCurrency(NaN)).toBe('–');
  });
});

/* ------------------------------------------------------------------ */
/*  formatPercent                                                      */
/* ------------------------------------------------------------------ */

describe('formatPercent', () => {
  it('formats decimal as percent', () => {
    const result = formatPercent(0.158);
    // Should produce something like "%15,8" or "15,8%" depending on locale
    expect(result).toContain('15');
    expect(result).toContain('%');
  });

  it('formats 1.0 as 100%', () => {
    const result = formatPercent(1);
    expect(result).toContain('100');
    expect(result).toContain('%');
  });

  it('formats 0', () => {
    const result = formatPercent(0);
    expect(result).toContain('0');
    expect(result).toContain('%');
  });

  it('handles NaN', () => {
    expect(formatPercent(NaN)).toBe('–');
  });
});

/* ------------------------------------------------------------------ */
/*  useChartFormatter                                                  */
/* ------------------------------------------------------------------ */

describe('useChartFormatter', () => {
  it('returns compact formatter by default', () => {
    const fmt = useChartFormatter();
    expect(fmt(1_000_000)).toBe('1M');
  });

  it('returns number formatter', () => {
    const fmt = useChartFormatter({ style: 'number' });
    const result = fmt(1234);
    expect(result).toBeTruthy();
  });

  it('returns percent formatter', () => {
    const fmt = useChartFormatter({ style: 'percent' });
    const result = fmt(0.5);
    expect(result).toContain('50');
    expect(result).toContain('%');
  });

  it('returns currency formatter', () => {
    const fmt = useChartFormatter({ style: 'currency' });
    const result = fmt(1000);
    expect(result).toBeTruthy();
    expect(result).not.toBe('–');
  });
});
