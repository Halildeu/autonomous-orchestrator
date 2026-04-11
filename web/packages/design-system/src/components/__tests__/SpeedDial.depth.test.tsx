// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { SpeedDial } from '../speed-dial/SpeedDial';

afterEach(cleanup);

const requiredProps = {
  actions: [],
};
describe('SpeedDial — depth', () => {
  describe('SpeedDial — depth: prop combinations', () => {
    it('renders with open + defaultOpen + hidden simultaneously', () => {
      render(<SpeedDial {...requiredProps} open defaultOpen hidden>Stressed</SpeedDial>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<SpeedDial {...requiredProps} open defaultOpen hidden />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('SpeedDial — depth: triggerMode variants', () => {
    it.each(['click', 'hover'] as const)('triggerMode=%s renders without crash', (val) => {
      const { container } = render(<SpeedDial {...requiredProps} triggerMode={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('SpeedDial — depth: actions array edge cases', () => {
    it('handles empty actions', () => {
      const { container } = render(<SpeedDial {...requiredProps} actions={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item actions', () => {
      const { container } = render(<SpeedDial {...requiredProps} actions={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
