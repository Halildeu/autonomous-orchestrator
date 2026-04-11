// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ShellSidebar } from '../shell-sidebar/ShellSidebar';

afterEach(cleanup);

describe('ShellSidebar — depth', () => {
  describe('ShellSidebar — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<ShellSidebar />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<ShellSidebar />);
      cleanup();
      const { container: c2 } = render(<ShellSidebar />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
