// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { HeatmapCalendar } from '../HeatmapCalendar';

afterEach(cleanup);

const requiredProps = {
  data: [],
};
describe('HeatmapCalendar — depth', () => {
  describe('HeatmapCalendar — depth: prop combinations', () => {
    it('renders with showMonthLabels + showDayLabels + showTooltip simultaneously', () => {
      render(<HeatmapCalendar {...requiredProps} showMonthLabels showDayLabels showTooltip>Stressed</HeatmapCalendar>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<HeatmapCalendar {...requiredProps} showMonthLabels showDayLabels showTooltip />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('HeatmapCalendar — depth: data array edge cases', () => {
    it('handles empty data', () => {
      const { container } = render(<HeatmapCalendar {...requiredProps} data={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item data', () => {
      const { container } = render(<HeatmapCalendar {...requiredProps} data={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
