// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { List } from '../list/List';
import type { ListDensity, ListTone, ListItem, ListProps } from '../list/List';

describe('List — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<List {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(List.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<List {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<List {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<List {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _listdensity: ListDensity | undefined = undefined; void _listdensity;
    const _listtone: ListTone | undefined = undefined; void _listtone;
    const _listitem: ListItem | undefined = undefined; void _listitem;
    const _listprops: ListProps | undefined = undefined; void _listprops;
    expect(true).toBe(true);
  });
});
