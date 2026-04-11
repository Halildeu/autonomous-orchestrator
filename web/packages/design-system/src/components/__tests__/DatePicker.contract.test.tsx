// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { DatePicker } from '../date-picker/DatePicker';
import type { DatePickerMessages, DatePickerProps } from '../date-picker/DatePicker';

describe('DatePicker — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<DatePicker  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(DatePicker.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<DatePicker  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<DatePicker  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 9 optional)', () => {
    // All 9 optional props omitted — should not crash
    const { container } = render(<DatePicker  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _datepickermessages: DatePickerMessages | undefined = undefined; void _datepickermessages;
    const _datepickerprops: DatePickerProps | undefined = undefined; void _datepickerprops;
    expect(true).toBe(true);
  });
});
