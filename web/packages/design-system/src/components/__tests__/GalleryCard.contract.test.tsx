// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { GalleryCard } from '../grouped-card-gallery/GalleryCard';

describe('GalleryCard — contract', () => {
  const defaultProps = {
    item: { id: '1', title: 'Test Card', group: 'Default' },
  };

  it('renders without crash', () => {
    const { container } = render(<GalleryCard {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(GalleryCard.displayName).toBeTruthy();
  });
});
