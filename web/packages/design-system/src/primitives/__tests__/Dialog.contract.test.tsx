// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi, beforeAll } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Dialog } from '../dialog/Dialog';
import type { DialogSize, DialogSlot, DialogProps } from '../dialog/Dialog';

// jsdom does not implement showModal/close on HTMLDialogElement
beforeAll(() => {
  HTMLDialogElement.prototype.showModal = HTMLDialogElement.prototype.showModal || vi.fn();
  HTMLDialogElement.prototype.close = HTMLDialogElement.prototype.close || vi.fn();
});

describe('Dialog — contract', () => {
  const defaultProps = {
    open: true,
    onClose: vi.fn(),
  };

  it('renders without crash', () => {
    const { container } = render(<Dialog {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Dialog.displayName).toBeTruthy();
  });

  it('renders with only required props (3 required, 9 optional)', () => {
    // All 9 optional props omitted — should not crash
    const { container } = render(<Dialog {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _dialogsize: DialogSize | undefined = undefined; void _dialogsize;
    const _dialogslot: DialogSlot | undefined = undefined; void _dialogslot;
    const _dialogprops: DialogProps | undefined = undefined; void _dialogprops;
    expect(true).toBe(true);
  });
});
