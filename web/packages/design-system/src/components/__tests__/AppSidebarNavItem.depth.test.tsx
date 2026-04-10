// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { AppSidebarNavItem } from '../app-sidebar/AppSidebarNavItem';

afterEach(cleanup);

describe('AppSidebarNavItem — depth', () => {
  describe('AppSidebarNavItem — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<AppSidebarNavItem />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<AppSidebarNavItem />);
      cleanup();
      const { container: c2 } = render(<AppSidebarNavItem />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
