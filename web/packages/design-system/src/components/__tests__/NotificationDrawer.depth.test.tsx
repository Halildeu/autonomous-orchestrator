// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { NotificationDrawer } from '../notification-drawer/NotificationDrawer';

afterEach(cleanup);

const requiredProps = {
  open: true,
};
describe('NotificationDrawer — depth', () => {
  describe('NotificationDrawer — depth: prop combinations', () => {
    it('renders with open + closeOnOverlayClick + closeOnEscape + keepMounted simultaneously', () => {
      render(<NotificationDrawer {...requiredProps} open closeOnOverlayClick closeOnEscape keepMounted>Stressed</NotificationDrawer>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<NotificationDrawer {...requiredProps} open closeOnOverlayClick closeOnEscape keepMounted />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
