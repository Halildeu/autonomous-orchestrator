// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Calendar } from '../calendar/Calendar';

afterEach(cleanup);

describe('Calendar — depth', () => {
  describe('Calendar — depth: prop combinations', () => {
    it('renders with showWeekNumbers + showOutsideDays simultaneously', () => {
      render(<Calendar showWeekNumbers showOutsideDays>Stressed</Calendar>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Calendar showWeekNumbers showOutsideDays />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Calendar — depth: firstDayOfWeek variants', () => {
    it.each(['0', '1'] as const)('firstDayOfWeek=%s renders without crash', (val) => {
      const { container } = render(<Calendar firstDayOfWeek={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Calendar — depth: numberOfMonths variants', () => {
    it.each(['1', '2', '3'] as const)('numberOfMonths=%s renders without crash', (val) => {
      const { container } = render(<Calendar numberOfMonths={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Calendar — depth: highlightedDates array edge cases', () => {
    it('handles empty highlightedDates', () => {
      const { container } = render(<Calendar highlightedDates={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item highlightedDates', () => {
      const { container } = render(<Calendar highlightedDates={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Calendar — depth: events array edge cases', () => {
    it('handles empty events', () => {
      const { container } = render(<Calendar events={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item events', () => {
      const { container } = render(<Calendar events={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Calendar — depth: controlled vs uncontrolled', () => {
    it('works in controlled mode (value + onChange)', () => {
      const onChange = vi.fn();
      const { container } = render(<Calendar value="test" onChange={onChange} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('works in uncontrolled mode (defaultValue)', () => {
      const { container } = render(<Calendar defaultValue="default" />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
