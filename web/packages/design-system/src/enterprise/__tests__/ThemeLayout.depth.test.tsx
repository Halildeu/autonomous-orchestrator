// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ThemeLayout } from '../ThemeLayout';

afterEach(cleanup);

const requiredProps = {
  theme: undefined as any,
  slots: undefined as any,
};
describe('ThemeLayout — depth', () => {
  describe('ThemeLayout — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<ThemeLayout {...requiredProps} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<ThemeLayout {...requiredProps} />);
      cleanup();
      const { container: c2 } = render(<ThemeLayout {...requiredProps} />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
