// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ProcessFlow } from '../ProcessFlow';

afterEach(cleanup);

const requiredProps = {
  nodes: [],
  edges: [],
};
describe('ProcessFlow — depth', () => {
  describe('ProcessFlow — depth: orientation variants', () => {
    it.each(['horizontal', 'vertical'] as const)('orientation=%s renders without crash', (val) => {
      const { container } = render(<ProcessFlow {...requiredProps} orientation={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ProcessFlow — depth: nodes array edge cases', () => {
    it('handles empty nodes', () => {
      const { container } = render(<ProcessFlow {...requiredProps} nodes={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item nodes', () => {
      const { container } = render(<ProcessFlow {...requiredProps} nodes={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ProcessFlow — depth: edges array edge cases', () => {
    it('handles empty edges', () => {
      const { container } = render(<ProcessFlow {...requiredProps} edges={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item edges', () => {
      const { container } = render(<ProcessFlow {...requiredProps} edges={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
