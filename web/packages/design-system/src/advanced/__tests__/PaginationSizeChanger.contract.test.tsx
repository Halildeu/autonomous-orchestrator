// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { PaginationSizeChanger } from '../data-grid/PaginationSizeChanger';

describe('PaginationSizeChanger — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<PaginationSizeChanger  />);
    expect(container.firstElementChild).toBeTruthy();
  });
});
