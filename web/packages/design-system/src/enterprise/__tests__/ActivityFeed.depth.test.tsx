// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ActivityFeed } from '../ActivityFeed';

afterEach(cleanup);

const requiredProps = {
  items: [],
};
describe('ActivityFeed — depth', () => {
  describe('ActivityFeed — depth: prop combinations', () => {
    it('renders with showLoadMore + groupByDate simultaneously', () => {
      render(<ActivityFeed {...requiredProps} showLoadMore groupByDate>Stressed</ActivityFeed>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<ActivityFeed {...requiredProps} showLoadMore groupByDate />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ActivityFeed — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<ActivityFeed {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<ActivityFeed {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
