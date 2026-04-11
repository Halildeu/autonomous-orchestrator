// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Image } from '../image/Image';

afterEach(cleanup);

describe('Image — depth', () => {
  describe('Image — depth: prop combinations', () => {
    it('renders with lazy', () => {
      const { container } = render(<Image lazy />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Image — depth: width variants', () => {
    it.each(['number', 'string'] as const)('width=%s renders without crash', (val) => {
      const { container } = render(<Image width={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Image — depth: height variants', () => {
    it.each(['number', 'string'] as const)('height=%s renders without crash', (val) => {
      const { container } = render(<Image height={val} />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
