// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Breadcrumb } from '../breadcrumb/Breadcrumb';

afterEach(cleanup);

const requiredProps = {
  items: [],
};
describe('Breadcrumb — depth', () => {
  describe('Breadcrumb — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<Breadcrumb {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<Breadcrumb {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
