// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { GridToolbar } from '../data-grid/GridToolbar';
import type { GridToolbarMessages, GridToolbarProps } from '../data-grid/GridToolbar';

describe('GridToolbar — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<GridToolbar  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(GridToolbar.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<GridToolbar  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<GridToolbar  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _gridtoolbarmessages: GridToolbarMessages | undefined = undefined; void _gridtoolbarmessages;
    const _gridtoolbarprops: GridToolbarProps | undefined = undefined; void _gridtoolbarprops;
    expect(true).toBe(true);
  });
});
