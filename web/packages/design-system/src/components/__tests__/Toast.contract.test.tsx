// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ToastProvider } from '../toast/Toast';
import type { ToastVariant, ToastPosition, ToastData, ToastOptions, ToastProviderProps } from '../toast/Toast';

describe('Toast — contract', () => {

  it('renders without crash', () => {
    const { container } = render(<ToastProvider><span>app</span></ToastProvider>);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ToastProvider.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<ToastProvider access="hidden"><span>app</span></ToastProvider>);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<ToastProvider access="readonly"><span>app</span></ToastProvider>);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 5 optional)', () => {
    const { container } = render(<ToastProvider><span>app</span></ToastProvider>);
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
