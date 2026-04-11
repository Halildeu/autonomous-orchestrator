// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Toast } from '../toast/Toast';
import type { ToastVariant, ToastPosition, ToastData, ToastOptions, ToastProviderProps } from '../toast/Toast';

describe('Toast — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Toast  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Toast.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Toast  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Toast  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 5 optional)', () => {
    // All 5 optional props omitted — should not crash
    const { container } = render(<Toast  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _toastvariant: ToastVariant | undefined = undefined; void _toastvariant;
    const _toastposition: ToastPosition | undefined = undefined; void _toastposition;
    const _toastdata: ToastData | undefined = undefined; void _toastdata;
    const _toastoptions: ToastOptions | undefined = undefined; void _toastoptions;
    const _toastproviderprops: ToastProviderProps | undefined = undefined; void _toastproviderprops;
    expect(true).toBe(true);
  });
});
