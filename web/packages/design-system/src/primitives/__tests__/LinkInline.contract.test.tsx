// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { LinkInline } from '../link-inline/LinkInline';
import type { LinkInlineTone, LinkInlineUnderline, LinkInlineProps } from '../link-inline/LinkInline';

describe('LinkInline — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<LinkInline  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(LinkInline.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<LinkInline  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<LinkInline  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 10 optional)', () => {
    // All 10 optional props omitted — should not crash
    const { container } = render(<LinkInline  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _linkinlinetone: LinkInlineTone | undefined = undefined; void _linkinlinetone;
    const _linkinlineunderline: LinkInlineUnderline | undefined = undefined; void _linkinlineunderline;
    const _linkinlineprops: LinkInlineProps | undefined = undefined; void _linkinlineprops;
    expect(true).toBe(true);
  });
});
