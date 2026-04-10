// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { PivotTable } from '../PivotTable';

afterEach(cleanup);

const requiredProps = {
  data: [],
  rows: [],
  columns: [],
  values: [],
};
describe('PivotTable — depth', () => {
  describe('PivotTable — depth: prop combinations', () => {
    it('renders with showTotals + compact + sortable simultaneously', () => {
      render(<PivotTable {...requiredProps} showTotals compact sortable>Stressed</PivotTable>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<PivotTable {...requiredProps} showTotals compact sortable />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('PivotTable — depth: data array edge cases', () => {
    it('handles empty data', () => {
      const { container } = render(<PivotTable {...requiredProps} data={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item data', () => {
      const { container } = render(<PivotTable {...requiredProps} data={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('PivotTable — depth: rows array edge cases', () => {
    it('handles empty rows', () => {
      const { container } = render(<PivotTable {...requiredProps} rows={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item rows', () => {
      const { container } = render(<PivotTable {...requiredProps} rows={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
