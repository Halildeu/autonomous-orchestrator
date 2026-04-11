// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { Watermark } from '../watermark/Watermark';

afterEach(cleanup);

describe('Watermark — depth', () => {
  describe('Watermark — depth: children edge cases', () => {
    it('handles null children', () => {
      const { container } = render(<Watermark>{null}</Watermark>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles numeric zero children', () => {
      const { container } = render(<Watermark>{0}</Watermark>);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('handles empty string children', () => {
      const { container } = render(<Watermark>{''}</Watermark>);
      expect(container.firstElementChild).toBeTruthy();
    });
  });
});
