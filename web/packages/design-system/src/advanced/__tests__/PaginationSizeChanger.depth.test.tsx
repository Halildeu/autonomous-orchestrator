// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { PaginationSizeChanger } from '../data-grid/PaginationSizeChanger';

afterEach(cleanup);

describe('PaginationSizeChanger — depth', () => {
  describe('PaginationSizeChanger — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<PaginationSizeChanger />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<PaginationSizeChanger />);
      cleanup();
      const { container: c2 } = render(<PaginationSizeChanger />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
