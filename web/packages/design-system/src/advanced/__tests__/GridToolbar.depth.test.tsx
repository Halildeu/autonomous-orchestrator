// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { GridToolbar } from '../data-grid/GridToolbar';

afterEach(cleanup);

describe('GridToolbar — depth', () => {
  describe('GridToolbar — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<GridToolbar />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<GridToolbar />);
      cleanup();
      const { container: c2 } = render(<GridToolbar />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
