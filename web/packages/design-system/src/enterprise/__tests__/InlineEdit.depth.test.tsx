// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { InlineEdit } from '../InlineEdit';

afterEach(cleanup);

const requiredProps = {
  value: 'test',
  onSave: vi.fn(),
};
describe('InlineEdit — depth', () => {
  describe('InlineEdit — depth: options array edge cases', () => {
    it('handles empty options', () => {
      const { container } = render(<InlineEdit {...requiredProps} options={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item options', () => {
      const { container } = render(<InlineEdit {...requiredProps} options={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
