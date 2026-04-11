// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { GalleryGroup } from '../grouped-card-gallery/GalleryGroup';

afterEach(cleanup);

describe('GalleryGroup — depth', () => {
  describe('GalleryGroup — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<GalleryGroup />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<GalleryGroup />);
      cleanup();
      const { container: c2 } = render(<GalleryGroup />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
