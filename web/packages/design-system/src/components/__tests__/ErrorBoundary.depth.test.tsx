// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ErrorBoundary } from '../error-boundary/ErrorBoundary';

afterEach(cleanup);

describe('ErrorBoundary — depth', () => {
  describe('ErrorBoundary — depth: children edge cases', () => {
    it('handles null children', () => {
      const { container } = render(<ErrorBoundary>{null}</ErrorBoundary>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles numeric zero children', () => {
      const { container } = render(<ErrorBoundary>{0}</ErrorBoundary>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles empty string children', () => {
      const { container } = render(<ErrorBoundary>{''}</ErrorBoundary>);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
