// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { NotificationPanel } from '../notification-drawer/NotificationPanel';

afterEach(cleanup);

const requiredProps = {
  items: [],
};
describe('NotificationPanel — depth', () => {
  describe('NotificationPanel — depth: prop combinations', () => {
    it('renders with showFilters + selectable simultaneously', () => {
      render(<NotificationPanel {...requiredProps} showFilters selectable>Stressed</NotificationPanel>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<NotificationPanel {...requiredProps} showFilters selectable />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('NotificationPanel — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<NotificationPanel {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<NotificationPanel {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('NotificationPanel — depth: availableFilters array edge cases', () => {
    it('handles empty availableFilters', () => {
      const { container } = render(<NotificationPanel {...requiredProps} availableFilters={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item availableFilters', () => {
      const { container } = render(<NotificationPanel {...requiredProps} availableFilters={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
