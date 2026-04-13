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

import { ConnectedInput } from '../connected/ConnectedInput';
import type { ConnectedInputProps, ConnectedInputRef, ConnectedInputElement, ConnectedInputCSSProperties } from '../connected/ConnectedInput';

describe('ConnectedInput — contract', () => {
  const defaultProps = {
    name: 'test',
  };

  it('renders without crash', () => {
    const { container } = render(<ConnectedInput {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ConnectedInput.displayName).toBeTruthy();
  });

  it('renders with only required props (1 required, 5 optional)', () => {
    // All 5 optional props omitted — should not crash
    const { container } = render(<ConnectedInput {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _connectedinputprops: ConnectedInputProps | undefined = undefined; void _connectedinputprops;
    const _connectedinputref: ConnectedInputRef | undefined = undefined; void _connectedinputref;
    const _connectedinputelement: ConnectedInputElement | undefined = undefined; void _connectedinputelement;
    const _connectedinputcssproperties: ConnectedInputCSSProperties | undefined = undefined; void _connectedinputcssproperties;
    expect(true).toBe(true);
  });
});
