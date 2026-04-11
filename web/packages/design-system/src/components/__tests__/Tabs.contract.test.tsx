// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Tabs } from '../tabs/Tabs';
import type { TabsVariant, TabsSize, TabsDensity, TabItem, TabsSlot } from '../tabs/Tabs';

describe('Tabs — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<Tabs {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Tabs.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Tabs {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Tabs {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 10 optional)', () => {
    // All 10 optional props omitted — should not crash
    const { container } = render(<Tabs {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _tabsvariant: TabsVariant | undefined = undefined; void _tabsvariant;
    const _tabssize: TabsSize | undefined = undefined; void _tabssize;
    const _tabsdensity: TabsDensity | undefined = undefined; void _tabsdensity;
    const _tabitem: TabItem | undefined = undefined; void _tabitem;
    const _tabsslot: TabsSlot | undefined = undefined; void _tabsslot;
    expect(true).toBe(true);
  });
});
