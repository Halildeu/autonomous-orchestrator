// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ServerPaginationFooter } from '../data-grid/ServerPaginationFooter';

afterEach(cleanup);

const requiredProps = {
  gridApi: 'GridApi',
};
describe('ServerPaginationFooter — depth', () => {
  describe('ServerPaginationFooter — depth: prop combinations', () => {
    it('renders with showAllOption', () => {
      const { container } = render(<ServerPaginationFooter {...requiredProps} showAllOption />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ServerPaginationFooter — depth: pageSizeOptions array edge cases', () => {
    it('handles empty pageSizeOptions', () => {
      const { container } = render(<ServerPaginationFooter {...requiredProps} pageSizeOptions={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item pageSizeOptions', () => {
      const { container } = render(<ServerPaginationFooter {...requiredProps} pageSizeOptions={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
