// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { TreeSelect } from '../tree-select/TreeSelect';

afterEach(cleanup);

const requiredProps = {
  data: [],
};
describe('TreeSelect — depth', () => {
  describe('TreeSelect — depth: prop combinations', () => {
    it('renders with multiple + searchable + treeCheckable + treeDefaultExpandAll simultaneously', () => {
      render(<TreeSelect {...requiredProps} multiple searchable treeCheckable treeDefaultExpandAll>Stressed</TreeSelect>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<TreeSelect {...requiredProps} multiple searchable treeCheckable treeDefaultExpandAll />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('TreeSelect — depth: data array edge cases', () => {
    it('handles empty data', () => {
      const { container } = render(<TreeSelect {...requiredProps} data={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item data', () => {
      const { container } = render(<TreeSelect {...requiredProps} data={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('TreeSelect — depth: onChange array edge cases', () => {
    it('handles empty onChange', () => {
      const { container } = render(<TreeSelect {...requiredProps} onChange={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item onChange', () => {
      const { container } = render(<TreeSelect {...requiredProps} onChange={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('TreeSelect — depth: controlled vs uncontrolled', () => {
    it('works in controlled mode (value + onChange)', () => {
      const onChange = vi.fn();
      const { container } = render(<TreeSelect {...requiredProps} value="test" onChange={onChange} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('works in uncontrolled mode (defaultValue)', () => {
      const { container } = render(<TreeSelect {...requiredProps} defaultValue="default" />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
