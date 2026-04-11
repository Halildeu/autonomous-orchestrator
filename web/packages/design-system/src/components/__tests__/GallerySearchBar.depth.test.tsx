// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { GallerySearchBar } from '../grouped-card-gallery/GallerySearchBar';

afterEach(cleanup);

describe('GallerySearchBar — depth', () => {
  describe('GallerySearchBar — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<GallerySearchBar />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<GallerySearchBar />);
      cleanup();
      const { container: c2 } = render(<GallerySearchBar />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
