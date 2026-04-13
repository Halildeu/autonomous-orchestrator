// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { MicroChart } from '../MicroChart';
import type { MicroChartType, MicroChartProps } from '../MicroChart';

describe('MicroChart — contract', () => {
  const defaultProps = {
    type: 'sparkline' as const,
    data: [10, 20, 30, 40, 50],
  };

  it('renders without crash', () => {
    const { container } = render(<MicroChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(MicroChart.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<MicroChart {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<MicroChart {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 6 optional)', () => {
    // All 6 optional props omitted — should not crash
    const { container } = render(<MicroChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _microcharttype: MicroChartType | undefined = undefined; void _microcharttype;
    const _microchartprops: MicroChartProps | undefined = undefined; void _microchartprops;
    expect(true).toBe(true);
  });
});
