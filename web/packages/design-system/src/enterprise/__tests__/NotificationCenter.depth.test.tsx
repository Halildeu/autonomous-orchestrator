// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { NotificationCenter } from '../NotificationCenter';

afterEach(cleanup);

const requiredProps = {
  notifications: [],
};
describe('NotificationCenter — depth', () => {
  describe('NotificationCenter — depth: prop combinations', () => {
    it('renders with groupByType', () => {
      const { container } = render(<NotificationCenter {...requiredProps} groupByType />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('NotificationCenter — depth: notifications array edge cases', () => {
    it('handles empty notifications', () => {
      const { container } = render(<NotificationCenter {...requiredProps} notifications={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item notifications', () => {
      const { container } = render(<NotificationCenter {...requiredProps} notifications={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
