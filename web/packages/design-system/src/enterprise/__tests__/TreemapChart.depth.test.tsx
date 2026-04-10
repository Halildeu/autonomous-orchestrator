// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { TreemapChart } from '../TreemapChart';

afterEach(cleanup);

const requiredProps = {
  items: [],
};
describe('TreemapChart — depth', () => {
  describe('TreemapChart — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<TreemapChart {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<TreemapChart {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('TreemapChart — depth: palette array edge cases', () => {
    it('handles empty palette', () => {
      const { container } = render(<TreemapChart {...requiredProps} palette={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item palette', () => {
      const { container } = render(<TreemapChart {...requiredProps} palette={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
