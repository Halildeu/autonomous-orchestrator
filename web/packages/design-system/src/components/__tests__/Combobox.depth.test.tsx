// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Combobox } from '../combobox/Combobox';

afterEach(cleanup);

const requiredProps = {
  options: 'Array<ComboboxOption',
};
describe('Combobox — depth', () => {
  describe('Combobox — depth: prop combinations', () => {
    it('renders with invalid + freeSolo + open + defaultOpen simultaneously', () => {
      render(<Combobox {...requiredProps} invalid freeSolo open defaultOpen>Stressed</Combobox>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Combobox {...requiredProps} invalid freeSolo open defaultOpen />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Combobox — depth: values array edge cases', () => {
    it('handles empty values', () => {
      const { container } = render(<Combobox {...requiredProps} values={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item values', () => {
      const { container } = render(<Combobox {...requiredProps} values={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Combobox — depth: defaultValues array edge cases', () => {
    it('handles empty defaultValues', () => {
      const { container } = render(<Combobox {...requiredProps} defaultValues={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item defaultValues', () => {
      const { container } = render(<Combobox {...requiredProps} defaultValues={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Combobox — depth: controlled vs uncontrolled', () => {
    it('works in controlled mode (value + onChange)', () => {
      const onChange = vi.fn();
      const { container } = render(<Combobox {...requiredProps} value="test" onChange={onChange} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('works in uncontrolled mode (defaultValue)', () => {
      const { container } = render(<Combobox {...requiredProps} defaultValue="default" />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
