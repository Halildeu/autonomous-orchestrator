// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { WaterfallChart } from '../WaterfallChart';
import type { WaterfallItem, WaterfallChartProps } from '../WaterfallChart';

describe('WaterfallChart — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<WaterfallChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(WaterfallChart.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<WaterfallChart {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<WaterfallChart {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 6 optional)', () => {
    // All 6 optional props omitted — should not crash
    const { container } = render(<WaterfallChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _waterfallitem: WaterfallItem | undefined = undefined; void _waterfallitem;
    const _waterfallchartprops: WaterfallChartProps | undefined = undefined; void _waterfallchartprops;
    expect(true).toBe(true);
  });
});
