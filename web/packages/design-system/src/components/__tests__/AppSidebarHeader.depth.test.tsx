// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { AppSidebarHeader } from '../app-sidebar/AppSidebarHeader';

afterEach(cleanup);

describe('AppSidebarHeader — depth', () => {
  describe('AppSidebarHeader — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<AppSidebarHeader />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<AppSidebarHeader />);
      cleanup();
      const { container: c2 } = render(<AppSidebarHeader />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
