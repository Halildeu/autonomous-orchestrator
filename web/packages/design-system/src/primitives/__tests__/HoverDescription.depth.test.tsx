// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { HoverDescription } from '../hover-description/HoverDescription';

afterEach(cleanup);

const requiredProps = {
  description: 'test',
};
describe('HoverDescription — depth', () => {
  describe('HoverDescription — depth: children edge cases', () => {
    it('handles null children', () => {
      const { container } = render(<HoverDescription {...requiredProps}>{null}</HoverDescription>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles numeric zero children', () => {
      const { container } = render(<HoverDescription {...requiredProps}>{0}</HoverDescription>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles empty string children', () => {
      const { container } = render(<HoverDescription {...requiredProps}>{''}</HoverDescription>);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
