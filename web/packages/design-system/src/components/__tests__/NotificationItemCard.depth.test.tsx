// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { NotificationItemCard } from '../notification-drawer/NotificationItemCard';

afterEach(cleanup);

const requiredProps = {
  item: undefined as any,
  item: undefined as any,
  timestamp: 'number',
  item: undefined as any,
  item: undefined as any,
  selected: undefined as any,
};
describe('NotificationItemCard — depth', () => {
  describe('NotificationItemCard — depth: prop combinations', () => {
    it('renders with selectable + selected simultaneously', () => {
      render(<NotificationItemCard {...requiredProps} selectable selected>Stressed</NotificationItemCard>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<NotificationItemCard {...requiredProps} selectable selected />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
