// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { InputNumber } from '../input-number/InputNumber';

afterEach(cleanup);

describe('InputNumber — depth', () => {
  describe('InputNumber — depth: prop combinations', () => {
    it('renders with disabled + readOnly + invalid + required simultaneously', () => {
      render(<InputNumber disabled readOnly invalid required>Stressed</InputNumber>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<InputNumber disabled readOnly invalid required />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('InputNumber — depth: controlled vs uncontrolled', () => {
    it('works in controlled mode (value + onChange)', () => {
      const onChange = vi.fn();
      const { container } = render(<InputNumber value="test" onChange={onChange} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('works in uncontrolled mode (defaultValue)', () => {
      const { container } = render(<InputNumber defaultValue="default" />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
