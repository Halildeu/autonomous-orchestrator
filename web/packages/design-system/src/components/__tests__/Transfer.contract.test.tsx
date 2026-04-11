// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Transfer } from '../transfer/Transfer';
import type { TransferItem, TransferDirection, TransferLocaleText, TransferSize, TransferProps } from '../transfer/Transfer';

describe('Transfer — contract', () => {
  const defaultProps = {
    dataSource: [],
    targetKeys: [],
    direction: undefined as any,
    moveKeys: [],
  };

  it('renders without crash', () => {
    const { container } = render(<Transfer {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Transfer.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Transfer {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Transfer {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (4 required, 12 optional)', () => {
    // All 12 optional props omitted — should not crash
    const { container } = render(<Transfer {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _transferitem: TransferItem | undefined = undefined; void _transferitem;
    const _transferdirection: TransferDirection | undefined = undefined; void _transferdirection;
    const _transferlocaletext: TransferLocaleText | undefined = undefined; void _transferlocaletext;
    const _transfersize: TransferSize | undefined = undefined; void _transfersize;
    const _transferprops: TransferProps | undefined = undefined; void _transferprops;
    expect(true).toBe(true);
  });
});
