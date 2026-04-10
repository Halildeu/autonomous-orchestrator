// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { RadarChart } from '../RadarChart';

afterEach(cleanup);

const requiredProps = {
  axes: [],
  series: [],
};
describe('RadarChart — depth', () => {
  describe('RadarChart — depth: prop combinations', () => {
    it('renders with showLabels + showLegend + showTooltip simultaneously', () => {
      render(<RadarChart {...requiredProps} showLabels showLegend showTooltip>Stressed</RadarChart>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<RadarChart {...requiredProps} showLabels showLegend showTooltip />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('RadarChart — depth: axes array edge cases', () => {
    it('handles empty axes', () => {
      const { container } = render(<RadarChart {...requiredProps} axes={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item axes', () => {
      const { container } = render(<RadarChart {...requiredProps} axes={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('RadarChart — depth: series array edge cases', () => {
    it('handles empty series', () => {
      const { container } = render(<RadarChart {...requiredProps} series={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item series', () => {
      const { container } = render(<RadarChart {...requiredProps} series={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
