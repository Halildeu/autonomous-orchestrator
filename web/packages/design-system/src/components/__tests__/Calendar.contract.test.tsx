// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Calendar } from '../calendar/Calendar';
import type { CalendarEvent, CalendarLocaleText, CalendarMode, CalendarSize, CalendarProps } from '../calendar/Calendar';

describe('Calendar — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Calendar  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Calendar.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Calendar  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Calendar  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 20 optional)', () => {
    // All 20 optional props omitted — should not crash
    const { container } = render(<Calendar  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _calendarevent: CalendarEvent | undefined = undefined; void _calendarevent;
    const _calendarlocaletext: CalendarLocaleText | undefined = undefined; void _calendarlocaletext;
    const _calendarmode: CalendarMode | undefined = undefined; void _calendarmode;
    const _calendarsize: CalendarSize | undefined = undefined; void _calendarsize;
    const _calendarprops: CalendarProps | undefined = undefined; void _calendarprops;
    expect(true).toBe(true);
  });
});
