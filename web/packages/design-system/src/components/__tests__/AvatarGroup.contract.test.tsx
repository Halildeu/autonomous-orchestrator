// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { AvatarGroup } from '../avatar-group/AvatarGroup';
import type { AvatarGroupItem, AvatarGroupSize, AvatarGroupShape, AvatarGroupSpacing, AvatarGroupProps } from '../avatar-group/AvatarGroup';

describe('AvatarGroup — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<AvatarGroup {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(AvatarGroup.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<AvatarGroup {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<AvatarGroup {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<AvatarGroup {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _avatargroupitem: AvatarGroupItem | undefined = undefined; void _avatargroupitem;
    const _avatargroupsize: AvatarGroupSize | undefined = undefined; void _avatargroupsize;
    const _avatargroupshape: AvatarGroupShape | undefined = undefined; void _avatargroupshape;
    const _avatargroupspacing: AvatarGroupSpacing | undefined = undefined; void _avatargroupspacing;
    const _avatargroupprops: AvatarGroupProps | undefined = undefined; void _avatargroupprops;
    expect(true).toBe(true);
  });
});
