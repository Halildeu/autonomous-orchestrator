// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { IconButton } from '../icon-button/IconButton';
import type { IconButtonVariant, IconButtonSize, IconButtonProps } from '../icon-button/IconButton';

describe('IconButton — contract', () => {
  const defaultProps = {
    icon: 'content',
    label: 'test',
  };

  it('renders without crash', () => {
    const { container } = render(<IconButton {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(IconButton.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<IconButton {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<IconButton {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 4 optional)', () => {
    // All 4 optional props omitted — should not crash
    const { container } = render(<IconButton {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _iconbuttonvariant: IconButtonVariant | undefined = undefined; void _iconbuttonvariant;
    const _iconbuttonsize: IconButtonSize | undefined = undefined; void _iconbuttonsize;
    const _iconbuttonprops: IconButtonProps | undefined = undefined; void _iconbuttonprops;
    expect(true).toBe(true);
  });
});
