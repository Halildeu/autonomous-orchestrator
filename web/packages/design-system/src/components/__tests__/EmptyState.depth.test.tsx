// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { EmptyState } from '../empty-state/EmptyState';

afterEach(cleanup);

describe('EmptyState — depth', () => {
  describe('EmptyState — depth: prop combinations', () => {
    it('renders with compact', () => {
      const { container } = render(<EmptyState compact />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
