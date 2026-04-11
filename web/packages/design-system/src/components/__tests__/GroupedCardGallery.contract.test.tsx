// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { GroupedCardGallery } from '../grouped-card-gallery/GroupedCardGallery';

describe('GroupedCardGallery — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<GroupedCardGallery  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(GroupedCardGallery.displayName).toBeTruthy();
  });
});
