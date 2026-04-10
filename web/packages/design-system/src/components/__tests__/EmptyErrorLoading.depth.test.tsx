// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { EmptyErrorLoading } from '../empty-error-loading/EmptyErrorLoading';

afterEach(cleanup);

const requiredProps = {
  mode: undefined as any,
};
describe('EmptyErrorLoading — depth', () => {
  describe('EmptyErrorLoading — depth: prop combinations', () => {
    it('renders with showSkeleton', () => {
      const { container } = render(<EmptyErrorLoading {...requiredProps} showSkeleton />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
