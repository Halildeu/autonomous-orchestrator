// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { AreaChart } from '../charts/AreaChart';
import type { AreaChartProps } from '../charts/AreaChart';

describe('AreaChart — contract', () => {
  const defaultProps = {
    series: [],
  };

  it('renders without crash', () => {
    const { container } = render(<AreaChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(AreaChart.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<AreaChart {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<AreaChart {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _areachartprops: AreaChartProps | undefined = undefined; void _areachartprops;
    expect(true).toBe(true);
  });
});
