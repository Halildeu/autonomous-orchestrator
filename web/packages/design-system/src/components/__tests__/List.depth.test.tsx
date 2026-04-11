// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { List } from '../list/List';

afterEach(cleanup);

const requiredProps = {
  items: [],
};
describe('List — depth', () => {
  describe('List — depth: prop combinations', () => {
    it('renders with bordered', () => {
      const { container } = render(<List {...requiredProps} bordered />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('List — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<List {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<List {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
