// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { TourCoachmarks } from '../tour-coachmarks/TourCoachmarks';

afterEach(cleanup);

const requiredProps = {
  steps: [],
};
describe('TourCoachmarks — depth', () => {
  describe('TourCoachmarks — depth: prop combinations', () => {
    it('renders with open + defaultOpen + allowSkip + showProgress simultaneously', () => {
      render(<TourCoachmarks {...requiredProps} open defaultOpen allowSkip showProgress>Stressed</TourCoachmarks>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<TourCoachmarks {...requiredProps} open defaultOpen allowSkip showProgress />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('TourCoachmarks — depth: mode variants', () => {
    it.each(['guided', 'readonly'] as const)('mode=%s renders without crash', (val) => {
      const { container } = render(<TourCoachmarks {...requiredProps} mode={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('TourCoachmarks — depth: steps array edge cases', () => {
    it('handles empty steps', () => {
      const { container } = render(<TourCoachmarks {...requiredProps} steps={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item steps', () => {
      const { container } = render(<TourCoachmarks {...requiredProps} steps={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
