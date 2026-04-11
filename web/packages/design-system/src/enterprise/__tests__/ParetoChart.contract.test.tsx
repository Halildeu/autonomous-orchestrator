// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ParetoChart } from '../ParetoChart';
import type { ParetoItem, ParetoChartProps } from '../ParetoChart';

describe('ParetoChart — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<ParetoChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ParetoChart.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ParetoChart {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ParetoChart {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<ParetoChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _paretoitem: ParetoItem | undefined = undefined; void _paretoitem;
    const _paretochartprops: ParetoChartProps | undefined = undefined; void _paretochartprops;
    expect(true).toBe(true);
  });
});
