// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { FieldControlShell } from '../_shared/FieldControlPrimitives';
import type { FieldSize, FieldTone, FieldDensity, FieldControlShellProps } from '../_shared/FieldControlPrimitives';

describe('FieldControlPrimitives — contract', () => {
  const defaultProps = {
    inputId: 'test',
  };

  it('renders without crash', () => {
    const { container } = render(<FieldControlShell {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(FieldControlShell.displayName).toBeTruthy();
  });

  it('renders with only required props (2 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<FieldControlShell {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _fieldsize: FieldSize | undefined = undefined; void _fieldsize;
    const _fieldtone: FieldTone | undefined = undefined; void _fieldtone;
    const _fielddensity: FieldDensity | undefined = undefined; void _fielddensity;
    const _fieldcontrolshellprops: FieldControlShellProps | undefined = undefined; void _fieldcontrolshellprops;
    expect(true).toBe(true);
  });
});
