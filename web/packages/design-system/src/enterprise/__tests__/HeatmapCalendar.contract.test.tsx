// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { HeatmapCalendar } from '../HeatmapCalendar';
import type { HeatmapDay, HeatmapCalendarProps } from '../HeatmapCalendar';

describe('HeatmapCalendar — contract', () => {
  const defaultProps = {
    data: [],
  };

  it('renders without crash', () => {
    const { container } = render(<HeatmapCalendar {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(HeatmapCalendar.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<HeatmapCalendar {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<HeatmapCalendar {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 10 optional)', () => {
    // All 10 optional props omitted — should not crash
    const { container } = render(<HeatmapCalendar {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _heatmapday: HeatmapDay | undefined = undefined; void _heatmapday;
    const _heatmapcalendarprops: HeatmapCalendarProps | undefined = undefined; void _heatmapcalendarprops;
    expect(true).toBe(true);
  });
});
