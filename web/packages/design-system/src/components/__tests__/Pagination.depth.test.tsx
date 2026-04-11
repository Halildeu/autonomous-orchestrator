// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Pagination } from '../pagination/Pagination';

afterEach(cleanup);

describe('Pagination — depth', () => {
  describe('Pagination — depth: prop combinations', () => {
    it('renders with showTotal', () => {
      const { container } = render(<Pagination showTotal />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
