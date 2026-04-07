/**
 * Tests for chart data validation & sanitization (utils/data-validation.ts)
 */
import { describe, it, expect } from 'vitest';
import {
  sanitizeNumber,
  clampValue,
  sanitizeDataPoints,
  sanitizeSeries,
  sanitizeNumbers,
  validateDataPoints,
  validateSeries,
} from '../utils/data-validation';

/* ------------------------------------------------------------------ */
/*  sanitizeNumber                                                     */
/* ------------------------------------------------------------------ */

describe('sanitizeNumber', () => {
  it('passes through valid numbers', () => {
    expect(sanitizeNumber(42)).toBe(42);
    expect(sanitizeNumber(0)).toBe(0);
    expect(sanitizeNumber(-5.5)).toBe(-5.5);
  });

  it('converts null/undefined to 0', () => {
    expect(sanitizeNumber(null)).toBe(0);
    expect(sanitizeNumber(undefined)).toBe(0);
  });

  it('converts NaN to 0', () => {
    expect(sanitizeNumber(NaN)).toBe(0);
  });

  it('converts Infinity to 0', () => {
    expect(sanitizeNumber(Infinity)).toBe(0);
    expect(sanitizeNumber(-Infinity)).toBe(0);
  });

  it('converts string numbers', () => {
    expect(sanitizeNumber('42')).toBe(42);
    expect(sanitizeNumber('3.14')).toBeCloseTo(3.14);
  });

  it('converts non-numeric strings to 0', () => {
    expect(sanitizeNumber('abc')).toBe(0);
  });
});

/* ------------------------------------------------------------------ */
/*  clampValue                                                         */
/* ------------------------------------------------------------------ */

describe('clampValue', () => {
  it('clamps below min', () => {
    expect(clampValue(-5, 0, 100)).toBe(0);
  });

  it('clamps above max', () => {
    expect(clampValue(150, 0, 100)).toBe(100);
  });

  it('passes through values in range', () => {
    expect(clampValue(50, 0, 100)).toBe(50);
  });

  it('handles edge values', () => {
    expect(clampValue(0, 0, 100)).toBe(0);
    expect(clampValue(100, 0, 100)).toBe(100);
  });
});

/* ------------------------------------------------------------------ */
/*  sanitizeDataPoints                                                 */
/* ------------------------------------------------------------------ */

describe('sanitizeDataPoints', () => {
  it('sanitizes valid data', () => {
    const result = sanitizeDataPoints([
      { label: 'A', value: 10 },
      { label: 'B', value: 20 },
    ]);
    expect(result).toHaveLength(2);
    expect(result[0].value).toBe(10);
  });

  it('coerces null/NaN values to 0', () => {
    const result = sanitizeDataPoints([
      { label: 'A', value: NaN },
      { label: 'B', value: null as unknown as number },
    ]);
    expect(result[0].value).toBe(0);
    expect(result[1].value).toBe(0);
  });

  it('handles missing labels', () => {
    const result = sanitizeDataPoints([
      { label: undefined as unknown as string, value: 10 },
    ]);
    expect(result[0].label).toBe('');
  });

  it('returns empty array for null input', () => {
    expect(sanitizeDataPoints(null as unknown as [])).toEqual([]);
    expect(sanitizeDataPoints(undefined as unknown as [])).toEqual([]);
  });

  it('preserves color property', () => {
    const result = sanitizeDataPoints([
      { label: 'A', value: 10, color: '#ff0000' },
    ]);
    expect(result[0].color).toBe('#ff0000');
  });
});

/* ------------------------------------------------------------------ */
/*  sanitizeSeries                                                     */
/* ------------------------------------------------------------------ */

describe('sanitizeSeries', () => {
  it('sanitizes valid series', () => {
    const result = sanitizeSeries([
      { name: 'Series A', data: [1, 2, 3] },
    ]);
    expect(result).toHaveLength(1);
    expect(result[0].data).toEqual([1, 2, 3]);
  });

  it('coerces NaN values in data arrays', () => {
    const result = sanitizeSeries([
      { name: 'S', data: [1, NaN, null as unknown as number, 4] },
    ]);
    expect(result[0].data).toEqual([1, 0, 0, 4]);
  });

  it('handles missing name', () => {
    const result = sanitizeSeries([
      { name: undefined as unknown as string, data: [1] },
    ]);
    expect(result[0].name).toBe('');
  });

  it('returns empty array for null input', () => {
    expect(sanitizeSeries(null as unknown as [])).toEqual([]);
  });
});

/* ------------------------------------------------------------------ */
/*  sanitizeNumbers                                                    */
/* ------------------------------------------------------------------ */

describe('sanitizeNumbers', () => {
  it('passes through valid numbers', () => {
    expect(sanitizeNumbers([1, 2, 3])).toEqual([1, 2, 3]);
  });

  it('coerces invalid values', () => {
    expect(sanitizeNumbers([1, NaN, null as unknown as number])).toEqual([1, 0, 0]);
  });

  it('returns empty for null', () => {
    expect(sanitizeNumbers(null as unknown as [])).toEqual([]);
  });
});

/* ------------------------------------------------------------------ */
/*  validateDataPoints                                                 */
/* ------------------------------------------------------------------ */

describe('validateDataPoints', () => {
  it('validates correct data', () => {
    const result = validateDataPoints([
      { label: 'A', value: 10 },
      { label: 'B', value: 20 },
    ]);
    expect(result.valid).toBe(true);
    expect(result.errors).toHaveLength(0);
  });

  it('rejects non-array', () => {
    const result = validateDataPoints('not an array');
    expect(result.valid).toBe(false);
    expect(result.errors).toContain('data must be an array');
  });

  it('rejects empty array', () => {
    const result = validateDataPoints([]);
    expect(result.valid).toBe(false);
  });

  it('reports invalid value types', () => {
    const result = validateDataPoints([
      { label: 'A', value: 'not a number' },
    ]);
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('not a valid number');
  });

  it('reports missing labels', () => {
    const result = validateDataPoints([
      { label: 123, value: 10 },
    ]);
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('not a string');
  });
});

/* ------------------------------------------------------------------ */
/*  validateSeries                                                     */
/* ------------------------------------------------------------------ */

describe('validateSeries', () => {
  it('validates correct series', () => {
    const result = validateSeries([
      { name: 'Series A', data: [1, 2, 3] },
    ]);
    expect(result.valid).toBe(true);
  });

  it('rejects non-array', () => {
    const result = validateSeries({});
    expect(result.valid).toBe(false);
  });

  it('reports missing data array', () => {
    const result = validateSeries([
      { name: 'S' },
    ]);
    expect(result.valid).toBe(false);
    expect(result.errors[0]).toContain('not an array');
  });
});
