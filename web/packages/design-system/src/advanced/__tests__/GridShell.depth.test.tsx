// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { GridShell } from '../data-grid/GridShell';

afterEach(cleanup);

describe('GridShell — depth', () => {
  describe('GridShell — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<GridShell />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<GridShell />);
      cleanup();
      const { container: c2 } = render(<GridShell />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
