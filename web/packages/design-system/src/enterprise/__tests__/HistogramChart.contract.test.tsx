// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { HistogramChart } from '../HistogramChart';
import type { HistogramBin, HistogramChartProps } from '../HistogramChart';

describe('HistogramChart — contract', () => {
  const defaultProps = {
    data: [],
  };

  it('renders without crash', () => {
    const { container } = render(<HistogramChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(HistogramChart.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<HistogramChart {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<HistogramChart {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 12 optional)', () => {
    // All 12 optional props omitted — should not crash
    const { container } = render(<HistogramChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _histogrambin: HistogramBin | undefined = undefined; void _histogrambin;
    const _histogramchartprops: HistogramChartProps | undefined = undefined; void _histogramchartprops;
    expect(true).toBe(true);
  });
});
