// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Avatar } from '../avatar/Avatar';

afterEach(cleanup);

describe('Avatar — depth', () => {
  describe('Avatar — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<Avatar />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<Avatar />);
      cleanup();
      const { container: c2 } = render(<Avatar />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
