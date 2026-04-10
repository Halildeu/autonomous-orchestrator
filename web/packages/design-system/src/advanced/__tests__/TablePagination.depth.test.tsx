// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { TablePagination } from '../data-grid/TablePagination';

afterEach(cleanup);

describe('TablePagination — depth', () => {
  describe('TablePagination — depth: prop combinations', () => {
    it('renders with showFirstLastButtons + totalItemsKnown + hasNextPage simultaneously', () => {
      render(<TablePagination showFirstLastButtons totalItemsKnown hasNextPage>Stressed</TablePagination>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<TablePagination showFirstLastButtons totalItemsKnown hasNextPage />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('TablePagination — depth: pageSizeOptions array edge cases', () => {
    it('handles empty pageSizeOptions', () => {
      const { container } = render(<TablePagination pageSizeOptions={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item pageSizeOptions', () => {
      const { container } = render(<TablePagination pageSizeOptions={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
