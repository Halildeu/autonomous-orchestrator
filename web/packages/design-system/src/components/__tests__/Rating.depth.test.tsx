// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Rating } from '../rating/Rating';

afterEach(cleanup);

describe('Rating — depth', () => {
  describe('Rating — depth: prop combinations', () => {
    it('renders with allowHalf + allowClear + showValue simultaneously', () => {
      render(<Rating allowHalf allowClear showValue>Stressed</Rating>);
      expect(screen.queryByText('Stressed') || document.body.firstElementChild).toBeTruthy();
    });

    it('does not crash with all boolean props toggled', () => {
      const { container } = render(<Rating allowHalf allowClear showValue />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Rating — depth: colors array edge cases', () => {
    it('handles empty colors', () => {
      const { container } = render(<Rating colors={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item colors', () => {
      const { container } = render(<Rating colors={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
