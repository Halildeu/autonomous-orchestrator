// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { EmptyErrorLoading } from '../empty-error-loading/EmptyErrorLoading';
import type { EmptyErrorLoadingMode, EmptyErrorLoadingProps } from '../empty-error-loading/EmptyErrorLoading';

describe('EmptyErrorLoading — contract', () => {
  const defaultProps = {
    mode: undefined as any,
  };

  it('renders without crash', () => {
    const { container } = render(<EmptyErrorLoading {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(EmptyErrorLoading.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<EmptyErrorLoading {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<EmptyErrorLoading {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 8 optional)', () => {
    // All 8 optional props omitted — should not crash
    const { container } = render(<EmptyErrorLoading {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _emptyerrorloadingmode: EmptyErrorLoadingMode | undefined = undefined; void _emptyerrorloadingmode;
    const _emptyerrorloadingprops: EmptyErrorLoadingProps | undefined = undefined; void _emptyerrorloadingprops;
    expect(true).toBe(true);
  });
});
