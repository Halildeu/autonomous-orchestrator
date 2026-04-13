// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';

vi.mock('../FormContext', () => ({
  useFormContext: () => ({
    values: {}, errors: {}, touched: {}, dirtyFields: {},
    access: 'normal', mode: 'onBlur',
    setFieldValue: vi.fn(), setFieldTouched: vi.fn(),
    setFieldError: vi.fn(), clearFieldError: vi.fn(),
    validateField: vi.fn(() => null), validateForm: vi.fn(() => ({})),
    reset: vi.fn(), isValid: true, isDirty: false, isSubmitting: false, validator: null,
  }),
  FormContext: { displayName: 'FormContext' },
}));

import { ConnectedFormField } from '../ConnectedFormField';
import type { ConnectedFormFieldProps, ConnectedFormFieldRef, ConnectedFormFieldElement, ConnectedFormFieldCSSProperties } from '../ConnectedFormField';

describe('ConnectedFormField — contract', () => {
  const defaultProps = {
    name: 'test',
  };

  it('renders without crash', () => {
    const { container } = render(<ConnectedFormField {...defaultProps}><input /></ConnectedFormField>);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ConnectedFormField.displayName).toBeTruthy();
  });

  it('renders with only required props (2 required, 8 optional)', () => {
    // All 8 optional props omitted — should not crash
    const { container } = render(<ConnectedFormField {...defaultProps}><input /></ConnectedFormField>);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _connectedformfieldprops: ConnectedFormFieldProps | undefined = undefined; void _connectedformfieldprops;
    const _connectedformfieldref: ConnectedFormFieldRef | undefined = undefined; void _connectedformfieldref;
    const _connectedformfieldelement: ConnectedFormFieldElement | undefined = undefined; void _connectedformfieldelement;
    const _connectedformfieldcssproperties: ConnectedFormFieldCSSProperties | undefined = undefined; void _connectedformfieldcssproperties;
    expect(true).toBe(true);
  });
});
