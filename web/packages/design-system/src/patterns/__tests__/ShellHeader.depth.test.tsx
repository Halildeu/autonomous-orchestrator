// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ShellHeader } from '../shell-header/ShellHeader';

afterEach(cleanup);

describe('ShellHeader — depth', () => {
  describe('ShellHeader — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<ShellHeader />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<ShellHeader />);
      cleanup();
      const { container: c2 } = render(<ShellHeader />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
