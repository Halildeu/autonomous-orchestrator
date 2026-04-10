// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { AppSidebarSearch } from '../app-sidebar/AppSidebarSearch';

afterEach(cleanup);

describe('AppSidebarSearch — depth', () => {
  describe('AppSidebarSearch — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<AppSidebarSearch />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<AppSidebarSearch />);
      cleanup();
      const { container: c2 } = render(<AppSidebarSearch />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
