// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Divider } from '../divider/Divider';

afterEach(cleanup);

describe('Divider — depth', () => {
  describe('Divider — depth: orientation variants', () => {
    it.each(['horizontal', 'vertical'] as const)('orientation=%s renders without crash', (val) => {
      const { container } = render(<Divider orientation={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Divider — depth: spacing variants', () => {
    it.each(['none', 'sm', 'md', 'lg'] as const)('spacing=%s renders without crash', (val) => {
      const { container } = render(<Divider spacing={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
