// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { SankeyDiagram } from '../SankeyDiagram';

afterEach(cleanup);

const requiredProps = {
  nodes: [],
  links: [],
};
describe('SankeyDiagram — depth', () => {
  describe('SankeyDiagram — depth: prop combinations', () => {
    it('renders with showValues', () => {
      const { container } = render(<SankeyDiagram {...requiredProps} showValues />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('SankeyDiagram — depth: nodes array edge cases', () => {
    it('handles empty nodes', () => {
      const { container } = render(<SankeyDiagram {...requiredProps} nodes={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item nodes', () => {
      const { container } = render(<SankeyDiagram {...requiredProps} nodes={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('SankeyDiagram — depth: links array edge cases', () => {
    it('handles empty links', () => {
      const { container } = render(<SankeyDiagram {...requiredProps} links={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item links', () => {
      const { container } = render(<SankeyDiagram {...requiredProps} links={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
