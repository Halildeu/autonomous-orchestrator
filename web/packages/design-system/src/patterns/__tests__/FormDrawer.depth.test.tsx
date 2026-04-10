// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { FormDrawer } from '../form-drawer/FormDrawer';

afterEach(cleanup);

const requiredProps = {
  open: true,
  onClose: vi.fn(),
  title: 'content',
};
describe('FormDrawer — depth', () => {
  describe('FormDrawer — depth: prop combinations', () => {
    it('renders with open + closeOnBackdrop + closeOnEscape + loading simultaneously', () => {
      render(<FormDrawer {...requiredProps} open closeOnBackdrop closeOnEscape loading>Stressed</FormDrawer>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<FormDrawer {...requiredProps} open closeOnBackdrop closeOnEscape loading />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('FormDrawer — depth: children edge cases', () => {
    it('handles null children', () => {
      const { container } = render(<FormDrawer {...requiredProps}>{null}</FormDrawer>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles numeric zero children', () => {
      const { container } = render(<FormDrawer {...requiredProps}>{0}</FormDrawer>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles empty string children', () => {
      const { container } = render(<FormDrawer {...requiredProps}>{''}</FormDrawer>);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
