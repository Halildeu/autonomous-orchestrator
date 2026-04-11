// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Statistic } from '../statistic/Statistic';

afterEach(cleanup);

describe('Statistic — depth', () => {
  describe('Statistic — depth: prop combinations', () => {
    it('renders with loading', () => {
      const { container } = render(<Statistic loading />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Statistic — depth: value variants', () => {
    it.each(['number', 'string'] as const)('value=%s renders without crash', (val) => {
      const { container } = render(<Statistic value={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
