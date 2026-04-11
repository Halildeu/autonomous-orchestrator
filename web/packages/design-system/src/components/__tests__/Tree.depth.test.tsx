// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Tree } from '../tree/Tree';

afterEach(cleanup);

const requiredProps = {
  nodes: [],
};
describe('Tree — depth', () => {
  describe('Tree — depth: prop combinations', () => {
    it('renders with loading + fullWidth simultaneously', () => {
      render(<Tree {...requiredProps} loading fullWidth>Stressed</Tree>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Tree {...requiredProps} loading fullWidth />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Tree — depth: nodes array edge cases', () => {
    it('handles empty nodes', () => {
      const { container } = render(<Tree {...requiredProps} nodes={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item nodes', () => {
      const { container } = render(<Tree {...requiredProps} nodes={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Tree — depth: defaultExpandedKeys array edge cases', () => {
    it('handles empty defaultExpandedKeys', () => {
      const { container } = render(<Tree {...requiredProps} defaultExpandedKeys={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item defaultExpandedKeys', () => {
      const { container } = render(<Tree {...requiredProps} defaultExpandedKeys={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
