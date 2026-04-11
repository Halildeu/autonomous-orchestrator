// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ControlChart } from '../ControlChart';
import type { ControlChartPoint, ControlChartProps } from '../ControlChart';

describe('ControlChart — contract', () => {
  const defaultProps = {
    data: 'Array<{ x: string',
  };

  it('renders without crash', () => {
    const { container } = render(<ControlChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ControlChart.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ControlChart {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ControlChart {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _controlchartpoint: ControlChartPoint | undefined = undefined; void _controlchartpoint;
    const _controlchartprops: ControlChartProps | undefined = undefined; void _controlchartprops;
    expect(true).toBe(true);
  });
});
