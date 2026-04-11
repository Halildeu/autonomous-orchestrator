// @vitest-environment jsdom
// Generated depth test — regenerate: node scripts/ci/generate-depth-tests.mjs --write
import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { GalleryCard } from '../grouped-card-gallery/GalleryCard';

afterEach(cleanup);

describe('GalleryCard — depth', () => {
  describe('GalleryCard — depth: basic resilience', () => {
    it('renders without crash', () => {
      const { container } = render(<GalleryCard />);
      expect(container.firstElementChild).toBeTruthy();
    });

    it('renders twice without side effects', () => {
      const { container: c1 } = render(<GalleryCard />);
      cleanup();
      const { container: c2 } = render(<GalleryCard />);
      expect(c2.firstElementChild).toBeTruthy();
    });
  });
});
