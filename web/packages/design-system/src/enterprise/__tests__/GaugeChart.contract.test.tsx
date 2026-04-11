// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { GaugeChart } from '../GaugeChart';
import type { GaugeThreshold, GaugeChartProps } from '../GaugeChart';

describe('GaugeChart — contract', () => {
  const defaultProps = {
    value: 42,
  };

  it('renders without crash', () => {
    const { container } = render(<GaugeChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(GaugeChart.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<GaugeChart {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<GaugeChart {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 10 optional)', () => {
    // All 10 optional props omitted — should not crash
    const { container } = render(<GaugeChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _gaugethreshold: GaugeThreshold | undefined = undefined; void _gaugethreshold;
    const _gaugechartprops: GaugeChartProps | undefined = undefined; void _gaugechartprops;
    expect(true).toBe(true);
  });
});
