// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { DateRangePicker } from '../DateRangePicker';
import type { DateRange, PresetKey, DateRangePreset, DateRangePickerProps } from '../DateRangePicker';

describe('DateRangePicker — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<DateRangePicker  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(DateRangePicker.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<DateRangePicker  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<DateRangePicker  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 8 optional)', () => {
    // All 8 optional props omitted — should not crash
    const { container } = render(<DateRangePicker  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _daterange: DateRange | undefined = undefined; void _daterange;
    const _presetkey: PresetKey | undefined = undefined; void _presetkey;
    const _daterangepreset: DateRangePreset | undefined = undefined; void _daterangepreset;
    const _daterangepickerprops: DateRangePickerProps | undefined = undefined; void _daterangepickerprops;
    expect(true).toBe(true);
  });
});
