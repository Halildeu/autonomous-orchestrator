// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { QRCode } from '../qr-code/QRCode';
import type { QRErrorLevel, QRCodeProps } from '../qr-code/QRCode';

describe('QRCode — contract', () => {
  const defaultProps = {
    value: 'test',
  };

  it('renders without crash', () => {
    const { container } = render(<QRCode {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(QRCode.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<QRCode {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<QRCode {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 10 optional)', () => {
    // All 10 optional props omitted — should not crash
    const { container } = render(<QRCode {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _qrerrorlevel: QRErrorLevel | undefined = undefined; void _qrerrorlevel;
    const _qrcodeprops: QRCodeProps | undefined = undefined; void _qrcodeprops;
    expect(true).toBe(true);
  });
});
