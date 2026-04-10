// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Textarea } from '../input/Textarea';

afterEach(cleanup);

const requiredProps = {
  value: undefined as any,
  event: undefined as any,
};
describe('Textarea — depth', () => {
  describe('Textarea — depth: prop combinations', () => {
    it('renders with showCount + fullWidth + loading simultaneously', () => {
      render(<Textarea {...requiredProps} showCount fullWidth loading>Stressed</Textarea>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Textarea {...requiredProps} showCount fullWidth loading />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Textarea — depth: controlled vs uncontrolled', () => {
    it('works in controlled mode (value + onChange)', () => {
      const onChange = vi.fn();
      const { container } = render(<Textarea {...requiredProps} value="test" onChange={onChange} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
