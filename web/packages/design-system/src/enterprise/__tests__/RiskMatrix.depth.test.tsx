// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { RiskMatrix } from '../RiskMatrix';

afterEach(cleanup);

const requiredProps = {
  risks: [],
};
describe('RiskMatrix — depth', () => {
  describe('RiskMatrix — depth: prop combinations', () => {
    it('renders with showLegend', () => {
      const { container } = render(<RiskMatrix {...requiredProps} showLegend />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('RiskMatrix — depth: risks array edge cases', () => {
    it('handles empty risks', () => {
      const { container } = render(<RiskMatrix {...requiredProps} risks={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item risks', () => {
      const { container } = render(<RiskMatrix {...requiredProps} risks={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('RiskMatrix — depth: onCellClick array edge cases', () => {
    it('handles empty onCellClick', () => {
      const { container } = render(<RiskMatrix {...requiredProps} onCellClick={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item onCellClick', () => {
      const { container } = render(<RiskMatrix {...requiredProps} onCellClick={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
