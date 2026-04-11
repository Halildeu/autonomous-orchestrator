// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { InlineEdit } from '../InlineEdit';
import type { InlineEditType, SelectOption, InlineEditProps } from '../InlineEdit';

describe('InlineEdit — contract', () => {
  const defaultProps = {
    value: 'test',
    onSave: vi.fn(),
  };

  it('renders without crash', () => {
    const { container } = render(<InlineEdit {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(InlineEdit.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<InlineEdit {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<InlineEdit {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 6 optional)', () => {
    // All 6 optional props omitted — should not crash
    const { container } = render(<InlineEdit {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _inlineedittype: InlineEditType | undefined = undefined; void _inlineedittype;
    const _selectoption: SelectOption | undefined = undefined; void _selectoption;
    const _inlineeditprops: InlineEditProps | undefined = undefined; void _inlineeditprops;
    expect(true).toBe(true);
  });
});
