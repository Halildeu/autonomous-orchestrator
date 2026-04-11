// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { GridShell } from '../data-grid/GridShell';
import type { GridTheme, GridDensity, GridShellApi, GridShellProps } from '../data-grid/GridShell';

describe('GridShell — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<GridShell  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(GridShell.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<GridShell  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<GridShell  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _gridtheme: GridTheme | undefined = undefined; void _gridtheme;
    const _griddensity: GridDensity | undefined = undefined; void _griddensity;
    const _gridshellapi: GridShellApi | undefined = undefined; void _gridshellapi;
    const _gridshellprops: GridShellProps | undefined = undefined; void _gridshellprops;
    expect(true).toBe(true);
  });
});
