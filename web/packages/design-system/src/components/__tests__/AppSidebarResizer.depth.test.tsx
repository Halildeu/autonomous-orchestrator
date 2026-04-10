// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { AppSidebarResizer } from '../app-sidebar/AppSidebarResizer';

afterEach(cleanup);

describe('AppSidebarResizer — depth', () => {
  describe('AppSidebarResizer — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<AppSidebarResizer />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<AppSidebarResizer />);
      cleanup();
      const { container: c2 } = render(<AppSidebarResizer />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
