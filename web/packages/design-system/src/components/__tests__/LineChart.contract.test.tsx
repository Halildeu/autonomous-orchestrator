// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { LineChart } from '../charts/LineChart';
import type { LineChartProps } from '../charts/LineChart';

describe('LineChart — contract', () => {
  const defaultProps = {
    series: [],
  };

  it('renders without crash', () => {
    const { container } = render(<LineChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(LineChart.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<LineChart {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<LineChart {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 4 optional)', () => {
    // All 4 optional props omitted — should not crash
    const { container } = render(<LineChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _linechartprops: LineChartProps | undefined = undefined; void _linechartprops;
    expect(true).toBe(true);
  });
});
