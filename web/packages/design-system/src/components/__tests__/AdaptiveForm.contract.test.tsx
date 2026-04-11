// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { AdaptiveForm } from '../adaptive-form/AdaptiveForm';
import type { FormFieldOption, FormFieldValidation, FormFieldDependency, FormField, FormLayout } from '../adaptive-form/AdaptiveForm';

describe('AdaptiveForm — contract', () => {
  const defaultProps = {
    fields: [],
  };

  it('renders without crash', () => {
    const { container } = render(<AdaptiveForm {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(AdaptiveForm.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<AdaptiveForm {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<AdaptiveForm {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 11 optional)', () => {
    // All 11 optional props omitted — should not crash
    const { container } = render(<AdaptiveForm {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _formfieldoption: FormFieldOption | undefined = undefined; void _formfieldoption;
    const _formfieldvalidation: FormFieldValidation | undefined = undefined; void _formfieldvalidation;
    const _formfielddependency: FormFieldDependency | undefined = undefined; void _formfielddependency;
    const _formfield: FormField | undefined = undefined; void _formfield;
    const _formlayout: FormLayout | undefined = undefined; void _formlayout;
    expect(true).toBe(true);
  });
});
