// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Toast } from '../toast/Toast';

afterEach(cleanup);

describe('Toast — depth', () => {
  describe('Toast — depth: prop combinations', () => {
    it('renders with animated', () => {
      const { container } = render(<Toast animated />);
      expect(container.firstElementChild).toBeTruthy();
    });
  });

  describe('Toast — depth: children edge cases', () => {
    it('handles null children', () => {
      const { container } = render(<Toast>{null}</Toast>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles numeric zero children', () => {
      const { container } = render(<Toast>{0}</Toast>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles empty string children', () => {
      const { container } = render(<Toast>{''}</Toast>);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
