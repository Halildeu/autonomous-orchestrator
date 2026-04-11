// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Grid } from '../grid/Grid';

afterEach(cleanup);

describe('Grid — depth', () => {
  describe('Grid — depth: as variants', () => {
    it.each(['div', 'section', 'article', 'main', 'nav'] as const)('as=%s renders without crash', (val) => {
      const { container } = render(<Grid as={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
