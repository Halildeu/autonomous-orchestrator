// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ValueStream } from '../ValueStream';

afterEach(cleanup);

const requiredProps = {
  steps: [],
};
describe('ValueStream — depth', () => {
  describe('ValueStream — depth: steps array edge cases', () => {
    it('handles empty steps', () => {
      const { container } = render(<ValueStream {...requiredProps} steps={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item steps', () => {
      const { container } = render(<ValueStream {...requiredProps} steps={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('ValueStream — depth: waits array edge cases', () => {
    it('handles empty waits', () => {
      const { container } = render(<ValueStream {...requiredProps} waits={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item waits', () => {
      const { container } = render(<ValueStream {...requiredProps} waits={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
