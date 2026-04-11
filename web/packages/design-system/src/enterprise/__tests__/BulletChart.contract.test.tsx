// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { BulletChart } from '../BulletChart';
import type { BulletChartRange, BulletChartProps } from '../BulletChart';

describe('BulletChart — contract', () => {
  const defaultProps = {
    value: 42,
    target: 42,
  };

  it('renders without crash', () => {
    const { container } = render(<BulletChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(BulletChart.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<BulletChart {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<BulletChart {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 11 optional)', () => {
    // All 11 optional props omitted — should not crash
    const { container } = render(<BulletChart {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _bulletchartrange: BulletChartRange | undefined = undefined; void _bulletchartrange;
    const _bulletchartprops: BulletChartProps | undefined = undefined; void _bulletchartprops;
    expect(true).toBe(true);
  });
});
