// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { AppSidebarSection } from '../app-sidebar/AppSidebarSection';

afterEach(cleanup);

describe('AppSidebarSection — depth', () => {
  describe('AppSidebarSection — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<AppSidebarSection />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<AppSidebarSection />);
      cleanup();
      const { container: c2 } = render(<AppSidebarSection />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
