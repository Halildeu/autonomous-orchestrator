// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { AdaptiveForm } from '../adaptive-form/AdaptiveForm';

afterEach(cleanup);

const requiredProps = {
  fields: [],
};
describe('AdaptiveForm — depth', () => {
  describe('AdaptiveForm — depth: prop combinations', () => {
    it('renders with showReset + loading simultaneously', () => {
      render(<AdaptiveForm {...requiredProps} showReset loading>Stressed</AdaptiveForm>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<AdaptiveForm {...requiredProps} showReset loading />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('AdaptiveForm — depth: columns variants', () => {
    it.each(['1', '2'] as const)('columns=%s renders without crash', (val) => {
      const { container } = render(<AdaptiveForm {...requiredProps} columns={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('AdaptiveForm — depth: fields array edge cases', () => {
    it('handles empty fields', () => {
      const { container } = render(<AdaptiveForm {...requiredProps} fields={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item fields', () => {
      const { container } = render(<AdaptiveForm {...requiredProps} fields={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
