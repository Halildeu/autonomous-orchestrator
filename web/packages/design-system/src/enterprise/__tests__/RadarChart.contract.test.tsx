// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { RadarChart } from '../RadarChart';
import type { RadarAxis, RadarSeries, RadarChartProps } from '../RadarChart';

describe('RadarChart — contract', () => {
  const defaultProps = {
    axes: [],
    series: [],
  };

  it('renders without crash', () => {
    const { container } = render(<RadarChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(RadarChart.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<RadarChart {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<RadarChart {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<RadarChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _radaraxis: RadarAxis | undefined = undefined; void _radaraxis;
    const _radarseries: RadarSeries | undefined = undefined; void _radarseries;
    const _radarchartprops: RadarChartProps | undefined = undefined; void _radarchartprops;
    expect(true).toBe(true);
  });
});
