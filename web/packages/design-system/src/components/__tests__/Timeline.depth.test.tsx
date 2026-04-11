// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Timeline } from '../timeline/Timeline';

afterEach(cleanup);

const requiredProps = {
  key: undefined as any,
};
describe('Timeline — depth', () => {
  describe('Timeline — depth: prop combinations', () => {
    it('renders with pending', () => {
      const { container } = render(<Timeline {...requiredProps} pending />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Timeline — depth: children edge cases', () => {
    it('handles null children', () => {
      const { container } = render(<Timeline {...requiredProps}>{null}</Timeline>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles numeric zero children', () => {
      const { container } = render(<Timeline {...requiredProps}>{0}</Timeline>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles empty string children', () => {
      const { container } = render(<Timeline {...requiredProps}>{''}</Timeline>);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
