// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { DataExportDialog } from '../DataExportDialog';

afterEach(cleanup);

const requiredProps = {
  open: true,
  onClose: vi.fn(),
  onExport: undefined as any,
};
describe('DataExportDialog — depth', () => {
  describe('DataExportDialog — depth: prop combinations', () => {
    it('renders with open', () => {
      const { container } = render(<DataExportDialog {...requiredProps} open />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
