// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Tag } from '../tag/Tag';
import type { TagVariant, TagSize, TagProps } from '../tag/Tag';

describe('Tag — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Tag  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Tag.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Tag  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Tag  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 9 optional)', () => {
    // All 9 optional props omitted — should not crash
    const { container } = render(<Tag  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _tagvariant: TagVariant | undefined = undefined; void _tagvariant;
    const _tagsize: TagSize | undefined = undefined; void _tagsize;
    const _tagprops: TagProps | undefined = undefined; void _tagprops;
    expect(true).toBe(true);
  });
});
