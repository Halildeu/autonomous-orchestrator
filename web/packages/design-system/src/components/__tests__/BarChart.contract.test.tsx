// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { BarChart } from '../charts/BarChart';
import type { BarChartProps } from '../charts/BarChart';

describe('BarChart — contract', () => {
  const defaultProps = {
    data: [],
  };

  it('renders without crash', () => {
    const { container } = render(<BarChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(BarChart.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<BarChart {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<BarChart {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 13 optional)', () => {
    // All 13 optional props omitted — should not crash
    const { container } = render(<BarChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _barchartprops: BarChartProps | undefined = undefined; void _barchartprops;
    expect(true).toBe(true);
  });
});
