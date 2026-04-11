// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Alert } from '../alert/Alert';
import type { AlertVariant, AlertProps } from '../alert/Alert';

describe('Alert — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Alert  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Alert.displayName).toBeTruthy();
  });

  it('renders with only required props (0 required, 8 optional)', () => {
    // All 8 optional props omitted — should not crash
    const { container } = render(<Alert  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _alertvariant: AlertVariant | undefined = undefined; void _alertvariant;
    const _alertprops: AlertProps | undefined = undefined; void _alertprops;
    expect(true).toBe(true);
  });
});
