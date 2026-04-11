// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Button } from '../button/Button';

afterEach(cleanup);

describe('Button — depth', () => {
  describe('Button — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<Button />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<Button />);
      cleanup();
      const { container: c2 } = render(<Button />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
