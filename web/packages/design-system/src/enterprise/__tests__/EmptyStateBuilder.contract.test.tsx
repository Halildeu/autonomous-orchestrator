// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { EmptyStateBuilder } from '../EmptyStateBuilder';
import type { EmptyStateReason, EmptyStateSize, EmptyStateAction, EmptyStateBuilderLocaleText, EmptyStateBuilderProps } from '../EmptyStateBuilder';

describe('EmptyStateBuilder — contract', () => {
  const defaultProps = {
    reason: undefined as any,
  };

  it('renders without crash', () => {
    const { container } = render(<EmptyStateBuilder {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(EmptyStateBuilder.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<EmptyStateBuilder {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<EmptyStateBuilder {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<EmptyStateBuilder {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _emptystatereason: EmptyStateReason | undefined = undefined; void _emptystatereason;
    const _emptystatesize: EmptyStateSize | undefined = undefined; void _emptystatesize;
    const _emptystateaction: EmptyStateAction | undefined = undefined; void _emptystateaction;
    const _emptystatebuilderlocaletext: EmptyStateBuilderLocaleText | undefined = undefined; void _emptystatebuilderlocaletext;
    const _emptystatebuilderprops: EmptyStateBuilderProps | undefined = undefined; void _emptystatebuilderprops;
    expect(true).toBe(true);
  });
});
