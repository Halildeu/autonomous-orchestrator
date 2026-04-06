/**
 * Chart Data Validation & Sanitization
 *
 * Ensures chart data is safe and well-formed before passing to ECharts.
 * Prevents NaN/null/undefined from breaking chart rendering.
 */

import type { ChartDataPoint, ChartSeries } from '../types';

/* ------------------------------------------------------------------ */
/*  Primitive sanitizers                                                */
/* ------------------------------------------------------------------ */

/** Coerce a single value to a safe number: null/undefined/NaN → 0 */
export function sanitizeNumber(value: unknown): number {
  if (value == null) return 0;
  const n = Number(value);
  return isNaN(n) || !isFinite(n) ? 0 : n;
}

/** Clamp a value within [min, max]. */
export function clampValue(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

/* ------------------------------------------------------------------ */
/*  Array sanitizers                                                    */
/* ------------------------------------------------------------------ */

/**
 * Sanitize an array of ChartDataPoint — coerce null/NaN values to 0.
 * Returns a new array (immutable).
 */
export function sanitizeDataPoints(data: ChartDataPoint[]): ChartDataPoint[] {
  if (!data || !Array.isArray(data)) return [];
  return data.map(d => ({
    ...d,
    label: d.label ?? '',
    value: sanitizeNumber(d.value),
  }));
}

/**
 * Sanitize ChartSeries array — coerce null/NaN values within each series.
 */
export function sanitizeSeries(series: ChartSeries[]): ChartSeries[] {
  if (!series || !Array.isArray(series)) return [];
  return series.map(s => ({
    ...s,
    name: s.name ?? '',
    data: (s.data ?? []).map(v => sanitizeNumber(v)),
  }));
}

/**
 * Sanitize a flat number array (for heatmap tuples, scatter, etc.).
 */
export function sanitizeNumbers(values: number[]): number[] {
  if (!values || !Array.isArray(values)) return [];
  return values.map(v => sanitizeNumber(v));
}

/* ------------------------------------------------------------------ */
/*  Validation                                                         */
/* ------------------------------------------------------------------ */

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

/**
 * Validate ChartDataPoint array:
 *  - Non-empty
 *  - All values are finite numbers
 *  - All labels are strings
 */
export function validateDataPoints(data: unknown): ValidationResult {
  const errors: string[] = [];

  if (!Array.isArray(data)) {
    errors.push('data must be an array');
    return { valid: false, errors };
  }
  if (data.length === 0) {
    errors.push('data array is empty');
    return { valid: false, errors };
  }

  data.forEach((d, i) => {
    if (typeof d !== 'object' || d == null) {
      errors.push(`data[${i}] is not an object`);
      return;
    }
    const point = d as Record<string, unknown>;
    if (typeof point.label !== 'string') {
      errors.push(`data[${i}].label is not a string`);
    }
    if (typeof point.value !== 'number' || isNaN(point.value as number)) {
      errors.push(`data[${i}].value is not a valid number`);
    }
  });

  return { valid: errors.length === 0, errors };
}

/**
 * Validate ChartSeries array.
 */
export function validateSeries(series: unknown): ValidationResult {
  const errors: string[] = [];

  if (!Array.isArray(series)) {
    errors.push('series must be an array');
    return { valid: false, errors };
  }
  if (series.length === 0) {
    errors.push('series array is empty');
    return { valid: false, errors };
  }

  series.forEach((s, i) => {
    if (typeof s !== 'object' || s == null) {
      errors.push(`series[${i}] is not an object`);
      return;
    }
    const entry = s as Record<string, unknown>;
    if (typeof entry.name !== 'string') {
      errors.push(`series[${i}].name is not a string`);
    }
    if (!Array.isArray(entry.data)) {
      errors.push(`series[${i}].data is not an array`);
    }
  });

  return { valid: errors.length === 0, errors };
}
