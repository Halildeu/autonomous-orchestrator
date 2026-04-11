// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ServerPaginationFooter } from '../data-grid/ServerPaginationFooter';
import type { ServerPaginationFooterProps } from '../data-grid/ServerPaginationFooter';

describe('ServerPaginationFooter — contract', () => {
  const defaultProps = {
    gridApi: 'GridApi',
  };

  it('renders without crash', () => {
    const { container } = render(<ServerPaginationFooter {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ServerPaginationFooter.displayName).toBeTruthy();
  });

  it('renders with only required props (1 required, 4 optional)', () => {
    // All 4 optional props omitted — should not crash
    const { container } = render(<ServerPaginationFooter {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _serverpaginationfooterprops: ServerPaginationFooterProps | undefined = undefined; void _serverpaginationfooterprops;
    expect(true).toBe(true);
  });
});
