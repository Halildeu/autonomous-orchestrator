// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Stack } from '../stack/Stack';

afterEach(cleanup);

describe('Stack — depth', () => {
  describe('Stack — depth: prop combinations', () => {
    it('renders with wrap', () => {
      const { container } = render(<Stack wrap />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Stack — depth: as variants', () => {
    it.each(['div', 'section', 'article', 'nav', 'main', 'aside', 'ul', 'ol'] as const)('as=%s renders without crash', (val) => {
      const { container } = render(<Stack as={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
