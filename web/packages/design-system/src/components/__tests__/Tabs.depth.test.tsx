// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Tabs } from '../tabs/Tabs';

afterEach(cleanup);

const requiredProps = {
  items: [],
};
describe('Tabs — depth', () => {
  describe('Tabs — depth: prop combinations', () => {
    it('renders with fullWidth', () => {
      const { container } = render(<Tabs {...requiredProps} fullWidth />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Tabs — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<Tabs {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<Tabs {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
