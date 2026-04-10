// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { CommandPalette } from '../command-palette/CommandPalette';

afterEach(cleanup);

const requiredProps = {
  open: true,
  items: [],
};
describe('CommandPalette — depth', () => {
  describe('CommandPalette — depth: prop combinations', () => {
    it('renders with open', () => {
      const { container } = render(<CommandPalette {...requiredProps} open />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('CommandPalette — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<CommandPalette {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<CommandPalette {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
