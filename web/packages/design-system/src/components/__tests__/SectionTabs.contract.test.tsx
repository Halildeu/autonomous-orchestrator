// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { SectionTabs } from '../detail-section-tabs/SectionTabs';
import type { SectionTabsDensity, SectionTabsLayout, SectionTabsBreakpoint, SectionTabsDescriptionVisibility, SectionTabsDescriptionDisplay } from '../detail-section-tabs/SectionTabs';

describe('SectionTabs — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<SectionTabs {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(SectionTabs.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<SectionTabs {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<SectionTabs {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 11 optional)', () => {
    // All 11 optional props omitted — should not crash
    const { container } = render(<SectionTabs {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _sectiontabsdensity: SectionTabsDensity | undefined = undefined; void _sectiontabsdensity;
    const _sectiontabslayout: SectionTabsLayout | undefined = undefined; void _sectiontabslayout;
    const _sectiontabsbreakpoint: SectionTabsBreakpoint | undefined = undefined; void _sectiontabsbreakpoint;
    const _sectiontabsdescriptionvisibility: SectionTabsDescriptionVisibility | undefined = undefined; void _sectiontabsdescriptionvisibility;
    const _sectiontabsdescriptiondisplay: SectionTabsDescriptionDisplay | undefined = undefined; void _sectiontabsdescriptiondisplay;
    expect(true).toBe(true);
  });
});
