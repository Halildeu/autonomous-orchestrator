// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { AppSidebarNav } from '../app-sidebar/AppSidebarNav';

afterEach(cleanup);

describe('AppSidebarNav — depth', () => {
  describe('AppSidebarNav — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<AppSidebarNav />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<AppSidebarNav />);
      cleanup();
      const { container: c2 } = render(<AppSidebarNav />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
