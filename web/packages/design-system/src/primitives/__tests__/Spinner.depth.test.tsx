// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Spinner } from '../spinner/Spinner';

afterEach(cleanup);

describe('Spinner — depth', () => {
  describe('Spinner — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<Spinner />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<Spinner />);
      cleanup();
      const { container: c2 } = render(<Spinner />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
