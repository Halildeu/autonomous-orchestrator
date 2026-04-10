// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { StatusTimeline } from '../StatusTimeline';

afterEach(cleanup);

const requiredProps = {
  events: [],
};
describe('StatusTimeline — depth', () => {
  describe('StatusTimeline — depth: prop combinations', () => {
    it('renders with compact', () => {
      const { container } = render(<StatusTimeline {...requiredProps} compact />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('StatusTimeline — depth: orientation variants', () => {
    it.each(['horizontal', 'vertical'] as const)('orientation=%s renders without crash', (val) => {
      const { container } = render(<StatusTimeline {...requiredProps} orientation={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('StatusTimeline — depth: events array edge cases', () => {
    it('handles empty events', () => {
      const { container } = render(<StatusTimeline {...requiredProps} events={[]} />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles single-item events', () => {
      const { container } = render(<StatusTimeline {...requiredProps} events={[{}] as any} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
