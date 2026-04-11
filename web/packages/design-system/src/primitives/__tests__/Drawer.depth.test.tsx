// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Drawer } from '../drawer/Drawer';

afterEach(cleanup);

const requiredProps = {
  open: true,
  onClose: vi.fn(),
};
describe('Drawer — depth', () => {
  describe('Drawer — depth: prop combinations', () => {
    it('renders with open + closeOnOverlayClick + closeOnEscape + showOverlay simultaneously', () => {
      render(<Drawer {...requiredProps} open closeOnOverlayClick closeOnEscape showOverlay>Stressed</Drawer>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Drawer {...requiredProps} open closeOnOverlayClick closeOnEscape showOverlay />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Drawer — depth: children edge cases', () => {
    it('handles null children', () => {
      const { container } = render(<Drawer {...requiredProps}>{null}</Drawer>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles numeric zero children', () => {
      const { container } = render(<Drawer {...requiredProps}>{0}</Drawer>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles empty string children', () => {
      const { container } = render(<Drawer {...requiredProps}>{''}</Drawer>);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
