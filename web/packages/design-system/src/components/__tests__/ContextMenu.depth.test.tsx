// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ContextMenu } from '../context-menu/ContextMenu';

afterEach(cleanup);

const requiredProps = {
  items: [],
};
describe('ContextMenu — depth', () => {
  describe('ContextMenu — depth: prop combinations', () => {
    it('renders with disabled', () => {
      const { container } = render(<ContextMenu {...requiredProps} disabled />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ContextMenu — depth: children edge cases', () => {
    it('handles null children', () => {
      const { container } = render(<ContextMenu {...requiredProps}>{null}</ContextMenu>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles numeric zero children', () => {
      const { container } = render(<ContextMenu {...requiredProps}>{0}</ContextMenu>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles empty string children', () => {
      const { container } = render(<ContextMenu {...requiredProps}>{''}</ContextMenu>);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ContextMenu — depth: items array edge cases', () => {
    it('handles empty items', () => {
      const { container } = render(<ContextMenu {...requiredProps} items={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item items', () => {
      const { container } = render(<ContextMenu {...requiredProps} items={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
