// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { DetailSectionTabs } from '../detail-section-tabs/DetailSectionTabs';
import type { DetailSectionTabItem, DetailSectionTabsProps, DetailSectionTabsPropsType, DetailSectionTabItemType } from '../detail-section-tabs/DetailSectionTabs';

describe('DetailSectionTabs — contract', () => {
  const defaultProps = {
    tabs: [],
    activeTabId: 'test',
    onTabChange: vi.fn(),
  };

  it('renders without crash', () => {
    const { container } = render(<DetailSectionTabs {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(DetailSectionTabs.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<DetailSectionTabs {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<DetailSectionTabs {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (3 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<DetailSectionTabs {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _detailsectiontabitem: DetailSectionTabItem | undefined = undefined; void _detailsectiontabitem;
    const _detailsectiontabsprops: DetailSectionTabsProps | undefined = undefined; void _detailsectiontabsprops;
    const _detailsectiontabspropstype: DetailSectionTabsPropsType | undefined = undefined; void _detailsectiontabspropstype;
    const _detailsectiontabitemtype: DetailSectionTabItemType | undefined = undefined; void _detailsectiontabitemtype;
    expect(true).toBe(true);
  });
});
