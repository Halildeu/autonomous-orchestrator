// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { GallerySearchBar } from '../grouped-card-gallery/GallerySearchBar';

describe('GallerySearchBar — contract', () => {
  const defaultProps = {
    value: '',
    onChange: vi.fn(),
  };

  it('renders without crash', () => {
    const { container } = render(<GallerySearchBar {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(GallerySearchBar.displayName).toBeTruthy();
  });
});
