// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Text } from '../text/Text';

afterEach(cleanup);

describe('Text — depth', () => {
  describe('Text — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<Text />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<Text />);
      cleanup();
      const { container: c2 } = render(<Text />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
