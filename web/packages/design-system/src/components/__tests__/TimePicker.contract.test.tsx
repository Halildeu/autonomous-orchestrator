// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { TimePicker } from '../time-picker/TimePicker';
import type { TimePickerMessages, TimePickerProps } from '../time-picker/TimePicker';

describe('TimePicker — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<TimePicker  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(TimePicker.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<TimePicker  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<TimePicker  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 9 optional)', () => {
    // All 9 optional props omitted — should not crash
    const { container } = render(<TimePicker  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _timepickermessages: TimePickerMessages | undefined = undefined; void _timepickermessages;
    const _timepickerprops: TimePickerProps | undefined = undefined; void _timepickerprops;
    expect(true).toBe(true);
  });
});
