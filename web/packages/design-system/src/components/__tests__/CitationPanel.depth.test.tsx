// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { CitationPanel } from '../citation-panel/CitationPanel';

afterEach(cleanup);

const requiredProps = {
  items: [],
};
describe('CitationPanel — depth', () => {
  describe('CitationPanel — depth: prop combinations', () => {
    it('renders with compact', () => {
      const { container } = render(<CitationPanel {...requiredProps} compact />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('CitationPanel — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<CitationPanel {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<CitationPanel {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
