// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { PageHeader } from '../page-header/PageHeader';
import type { PageHeaderProps, PageHeaderTagItem, PageHeaderTagInput, PageHeaderStatItem, PageHeaderStatInput } from '../page-header/PageHeader';

describe('PageHeader — contract', () => {
  const defaultProps = {
    title: 'content',
  };

  it('renders without crash', () => {
    const { container } = render(<PageHeader {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(PageHeader.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<PageHeader {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<PageHeader {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 10 optional)', () => {
    // All 10 optional props omitted — should not crash
    const { container } = render(<PageHeader {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _pageheaderprops: PageHeaderProps | undefined = undefined; void _pageheaderprops;
    const _pageheadertagitem: PageHeaderTagItem | undefined = undefined; void _pageheadertagitem;
    const _pageheadertaginput: PageHeaderTagInput | undefined = undefined; void _pageheadertaginput;
    const _pageheaderstatitem: PageHeaderStatItem | undefined = undefined; void _pageheaderstatitem;
    const _pageheaderstatinput: PageHeaderStatInput | undefined = undefined; void _pageheaderstatinput;
    expect(true).toBe(true);
  });
});
