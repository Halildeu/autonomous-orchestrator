// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { AnchorToc } from '../anchor-toc/AnchorToc';
import type { AnchorTocDensity, AnchorTocItem, AnchorTocProps } from '../anchor-toc/AnchorToc';

describe('AnchorToc — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<AnchorToc {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(AnchorToc.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<AnchorToc {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<AnchorToc {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 11 optional)', () => {
    // All 11 optional props omitted — should not crash
    const { container } = render(<AnchorToc {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _anchortocdensity: AnchorTocDensity | undefined = undefined; void _anchortocdensity;
    const _anchortocitem: AnchorTocItem | undefined = undefined; void _anchortocitem;
    const _anchortocprops: AnchorTocProps | undefined = undefined; void _anchortocprops;
    expect(true).toBe(true);
  });
});
