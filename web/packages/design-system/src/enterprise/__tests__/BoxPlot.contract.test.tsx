// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { BoxPlot } from '../BoxPlot';
import type { BoxPlotData, BoxPlotProps } from '../BoxPlot';

describe('BoxPlot — contract', () => {
  const defaultProps = {
    data: [],
  };

  it('renders without crash', () => {
    const { container } = render(<BoxPlot {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(BoxPlot.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<BoxPlot {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<BoxPlot {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<BoxPlot {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _boxplotdata: BoxPlotData | undefined = undefined; void _boxplotdata;
    const _boxplotprops: BoxPlotProps | undefined = undefined; void _boxplotprops;
    expect(true).toBe(true);
  });
});
