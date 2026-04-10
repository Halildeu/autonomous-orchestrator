// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { EntityGridTemplate } from '../data-grid/EntityGridTemplate';

afterEach(cleanup);

describe('EntityGridTemplate — depth', () => {
  describe('EntityGridTemplate — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<EntityGridTemplate />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<EntityGridTemplate />);
      cleanup();
      const { container: c2 } = render(<EntityGridTemplate />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
