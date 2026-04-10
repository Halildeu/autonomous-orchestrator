// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { AppSidebarSeparator } from '../app-sidebar/AppSidebarSeparator';

afterEach(cleanup);

describe('AppSidebarSeparator — depth', () => {
  describe('AppSidebarSeparator — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<AppSidebarSeparator />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<AppSidebarSeparator />);
      cleanup();
      const { container: c2 } = render(<AppSidebarSeparator />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
