// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Flex } from '../flex/Flex';

afterEach(cleanup);

describe('Flex — depth', () => {
  describe('Flex — depth: prop combinations', () => {
    it('renders with inline', () => {
      const { container } = render(<Flex inline />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Flex — depth: as variants', () => {
    it.each(['div', 'section', 'article', 'nav', 'main', 'aside', 'header', 'footer', 'span'] as const)('as=%s renders without crash', (val) => {
      const { container } = render(<Flex as={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
