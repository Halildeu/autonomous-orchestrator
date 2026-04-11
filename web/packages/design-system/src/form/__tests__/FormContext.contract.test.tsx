// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { FormContext } from '../FormContext';
import type { FormContextValue, FormContextProps, FormFieldName, FormValidationMode } from '../FormContext';

describe('FormContext — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<FormContext  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(FormContext.displayName).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _formcontextvalue: FormContextValue | undefined = undefined; void _formcontextvalue;
    const _formcontextprops: FormContextProps | undefined = undefined; void _formcontextprops;
    const _formfieldname: FormFieldName | undefined = undefined; void _formfieldname;
    const _formvalidationmode: FormValidationMode | undefined = undefined; void _formvalidationmode;
    expect(true).toBe(true);
  });
});
