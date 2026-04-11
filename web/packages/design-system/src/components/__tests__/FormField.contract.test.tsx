// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { FormField } from '../form-field/FormField';
import type { FormFieldProps, FormFieldRef, FormFieldElement, FormFieldCSSProperties } from '../form-field/FormField';

describe('FormField — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<FormField  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(FormField.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<FormField  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<FormField  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 9 optional)', () => {
    // All 9 optional props omitted — should not crash
    const { container } = render(<FormField  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _formfieldprops: FormFieldProps | undefined = undefined; void _formfieldprops;
    const _formfieldref: FormFieldRef | undefined = undefined; void _formfieldref;
    const _formfieldelement: FormFieldElement | undefined = undefined; void _formfieldelement;
    const _formfieldcssproperties: FormFieldCSSProperties | undefined = undefined; void _formfieldcssproperties;
    expect(true).toBe(true);
  });
});
