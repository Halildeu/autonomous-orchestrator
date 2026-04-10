// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { TableSimple } from '../table-simple/TableSimple';

afterEach(cleanup);

describe('TableSimple — depth', () => {
  describe('TableSimple — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<TableSimple />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<TableSimple />);
      cleanup();
      const { container: c2 } = render(<TableSimple />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
