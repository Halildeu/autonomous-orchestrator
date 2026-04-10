// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ReportFilterPanel } from '../report-filter-panel/ReportFilterPanel';

afterEach(cleanup);

describe('ReportFilterPanel — depth', () => {
  describe('ReportFilterPanel — depth: prop combinations', () => {
    it('renders with loading', () => {
      const { container } = render(<ReportFilterPanel loading />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ReportFilterPanel — depth: children edge cases', () => {
    it('handles null children', () => {
      const { container } = render(<ReportFilterPanel>{null}</ReportFilterPanel>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles numeric zero children', () => {
      const { container } = render(<ReportFilterPanel>{0}</ReportFilterPanel>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles empty string children', () => {
      const { container } = render(<ReportFilterPanel>{''}</ReportFilterPanel>);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
