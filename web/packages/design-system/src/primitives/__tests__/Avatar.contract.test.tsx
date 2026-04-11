// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Avatar } from '../avatar/Avatar';
import type { AvatarSize, AvatarShape, AvatarProps } from '../avatar/Avatar';

describe('Avatar — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Avatar  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Avatar.displayName).toBeTruthy();
  });

  it('renders with only required props (0 required, 6 optional)', () => {
    // All 6 optional props omitted — should not crash
    const { container } = render(<Avatar  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _avatarsize: AvatarSize | undefined = undefined; void _avatarsize;
    const _avatarshape: AvatarShape | undefined = undefined; void _avatarshape;
    const _avatarprops: AvatarProps | undefined = undefined; void _avatarprops;
    expect(true).toBe(true);
  });
});
