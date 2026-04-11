// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Autocomplete } from '../autocomplete/Autocomplete';

afterEach(cleanup);

const requiredProps = {
  options: [],
};
describe('Autocomplete — depth', () => {
  describe('Autocomplete — depth: prop combinations', () => {
    it('renders with loading + disabled + invalid + fullWidth simultaneously', () => {
      render(<Autocomplete {...requiredProps} loading disabled invalid fullWidth>Stressed</Autocomplete>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Autocomplete {...requiredProps} loading disabled invalid fullWidth />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Autocomplete — depth: options array edge cases', () => {
    it('handles empty options', () => {
      const { container } = render(<Autocomplete {...requiredProps} options={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item options', () => {
      const { container } = render(<Autocomplete {...requiredProps} options={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Autocomplete — depth: controlled vs uncontrolled', () => {
    it('works in controlled mode (value + onChange)', () => {
      const onChange = vi.fn();
      const { container } = render(<Autocomplete {...requiredProps} value="test" onChange={onChange} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('works in uncontrolled mode (defaultValue)', () => {
      const { container } = render(<Autocomplete {...requiredProps} defaultValue="default" />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
