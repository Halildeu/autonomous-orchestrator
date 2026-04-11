// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { AppSidebarFooterStatus } from '../app-sidebar/AppSidebarFooterStatus';

afterEach(cleanup);

describe('AppSidebarFooterStatus — depth', () => {
  describe('AppSidebarFooterStatus — depth: prop combinations', () => {
    it('renders with pulse', () => {
      const { container } = render(<AppSidebarFooterStatus pulse />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
