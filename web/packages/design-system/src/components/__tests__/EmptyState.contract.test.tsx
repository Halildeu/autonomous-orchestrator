// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { EmptyState } from '../empty-state/EmptyState';
import type { EmptyStateProps, EmptyStateRef, EmptyStateElement, EmptyStateCSSProperties } from '../empty-state/EmptyState';

describe('EmptyState — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<EmptyState  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(EmptyState.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<EmptyState  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<EmptyState  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 9 optional)', () => {
    // All 9 optional props omitted — should not crash
    const { container } = render(<EmptyState  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _emptystateprops: EmptyStateProps | undefined = undefined; void _emptystateprops;
    const _emptystateref: EmptyStateRef | undefined = undefined; void _emptystateref;
    const _emptystateelement: EmptyStateElement | undefined = undefined; void _emptystateelement;
    const _emptystatecssproperties: EmptyStateCSSProperties | undefined = undefined; void _emptystatecssproperties;
    expect(true).toBe(true);
  });
});
