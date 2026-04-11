// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Radio } from '../radio/Radio';

afterEach(cleanup);

describe('Radio — depth', () => {
  describe('Radio — depth: prop combinations', () => {
    it('renders with loading', () => {
      const { container } = render(<Radio loading />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Radio — depth: density variants', () => {
    it.each(['compact', 'comfortable', 'spacious'] as const)('density=%s renders without crash', (val) => {
      const { container } = render(<Radio density={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
