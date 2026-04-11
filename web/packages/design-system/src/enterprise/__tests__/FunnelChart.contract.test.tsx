// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { FunnelChart } from '../FunnelChart';
import type { FunnelStage, FunnelChartProps } from '../FunnelChart';

describe('FunnelChart — contract', () => {
  const defaultProps = {
    stages: [],
  };

  it('renders without crash', () => {
    const { container } = render(<FunnelChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(FunnelChart.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<FunnelChart {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<FunnelChart {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 5 optional)', () => {
    // All 5 optional props omitted — should not crash
    const { container } = render(<FunnelChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _funnelstage: FunnelStage | undefined = undefined; void _funnelstage;
    const _funnelchartprops: FunnelChartProps | undefined = undefined; void _funnelchartprops;
    expect(true).toBe(true);
  });
});
