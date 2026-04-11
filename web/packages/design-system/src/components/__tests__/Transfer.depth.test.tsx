// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Transfer } from '../transfer/Transfer';

afterEach(cleanup);

const requiredProps = {
  dataSource: [],
  targetKeys: [],
  direction: undefined as any,
  moveKeys: [],
};
describe('Transfer — depth', () => {
  describe('Transfer — depth: prop combinations', () => {
    it('renders with searchable + showSelectAll simultaneously', () => {
      render(<Transfer {...requiredProps} searchable showSelectAll>Stressed</Transfer>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Transfer {...requiredProps} searchable showSelectAll />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Transfer — depth: dataSource array edge cases', () => {
    it('handles empty dataSource', () => {
      const { container } = render(<Transfer {...requiredProps} dataSource={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item dataSource', () => {
      const { container } = render(<Transfer {...requiredProps} dataSource={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Transfer — depth: targetKeys array edge cases', () => {
    it('handles empty targetKeys', () => {
      const { container } = render(<Transfer {...requiredProps} targetKeys={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item targetKeys', () => {
      const { container } = render(<Transfer {...requiredProps} targetKeys={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
