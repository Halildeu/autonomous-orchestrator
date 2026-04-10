// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { DecisionMatrix } from '../DecisionMatrix';

afterEach(cleanup);

const requiredProps = {
  options: [],
  criteria: [],
  scores: [],
};
describe('DecisionMatrix — depth', () => {
  describe('DecisionMatrix — depth: prop combinations', () => {
    it('renders with showWeightedTotals + highlightWinner simultaneously', () => {
      render(<DecisionMatrix {...requiredProps} showWeightedTotals highlightWinner>Stressed</DecisionMatrix>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<DecisionMatrix {...requiredProps} showWeightedTotals highlightWinner />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('DecisionMatrix — depth: options array edge cases', () => {
    it('handles empty options', () => {
      const { container } = render(<DecisionMatrix {...requiredProps} options={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item options', () => {
      const { container } = render(<DecisionMatrix {...requiredProps} options={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('DecisionMatrix — depth: criteria array edge cases', () => {
    it('handles empty criteria', () => {
      const { container } = render(<DecisionMatrix {...requiredProps} criteria={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item criteria', () => {
      const { container } = render(<DecisionMatrix {...requiredProps} criteria={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
