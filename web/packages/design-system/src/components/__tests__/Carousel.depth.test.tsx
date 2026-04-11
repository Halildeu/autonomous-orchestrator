// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Carousel } from '../carousel/Carousel';

afterEach(cleanup);

const requiredProps = {
  items: undefined as any,
};
describe('Carousel — depth', () => {
  describe('Carousel — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<Carousel {...requiredProps} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<Carousel {...requiredProps} />);
      cleanup();
      const { container: c2 } = render(<Carousel {...requiredProps} />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
