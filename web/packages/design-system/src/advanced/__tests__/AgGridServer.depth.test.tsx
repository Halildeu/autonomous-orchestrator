// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { AgGridServer } from '../data-grid/AgGridServer';

afterEach(cleanup);

const requiredProps = {
  columnDefs: [],
  getData: undefined as any,
};
describe('AgGridServer — depth', () => {
  describe('AgGridServer — depth: height variants', () => {
    it.each(['number', 'string'] as const)('height=%s renders without crash', (val) => {
      const { container } = render(<AgGridServer {...requiredProps} height={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
