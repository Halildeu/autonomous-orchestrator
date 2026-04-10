// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { DateRangePicker } from '../DateRangePicker';

afterEach(cleanup);

describe('DateRangePicker — depth', () => {
  describe('DateRangePicker — depth: disabledPresets array edge cases', () => {
    it('handles empty disabledPresets', () => {
      const { container } = render(<DateRangePicker disabledPresets={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item disabledPresets', () => {
      const { container } = render(<DateRangePicker disabledPresets={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('DateRangePicker — depth: controlled vs uncontrolled', () => {
    it('works in controlled mode (value + onChange)', () => {
      const onChange = vi.fn();
      const { container } = render(<DateRangePicker value="test" onChange={onChange} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
