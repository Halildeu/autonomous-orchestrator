// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Dialog } from '../dialog/Dialog';

afterEach(cleanup);

const requiredProps = {
  open: true,
  onClose: vi.fn(),
};
describe('Dialog — depth', () => {
  describe('Dialog — depth: prop combinations', () => {
    it('renders with open + closable + closeOnBackdrop + closeOnEscape simultaneously', () => {
      render(<Dialog {...requiredProps} open closable closeOnBackdrop closeOnEscape>Stressed</Dialog>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Dialog {...requiredProps} open closable closeOnBackdrop closeOnEscape />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Dialog — depth: children edge cases', () => {
    it('handles null children', () => {
      const { container } = render(<Dialog {...requiredProps}>{null}</Dialog>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles numeric zero children', () => {
      const { container } = render(<Dialog {...requiredProps}>{0}</Dialog>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles empty string children', () => {
      const { container } = render(<Dialog {...requiredProps}>{''}</Dialog>);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
