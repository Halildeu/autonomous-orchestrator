// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ConnectedCheckbox } from '../connected/ConnectedCheckbox';
import type { ConnectedCheckboxProps, ConnectedCheckboxRef, ConnectedCheckboxElement, ConnectedCheckboxCSSProperties } from '../connected/ConnectedCheckbox';

describe('ConnectedCheckbox — contract', () => {
  const defaultProps = {
    name: 'test',
  };

  it('renders without crash', () => {
    const { container } = render(<ConnectedCheckbox {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ConnectedCheckbox.displayName).toBeTruthy();
  });

  it('renders with only required props (1 required, 5 optional)', () => {
    // All 5 optional props omitted — should not crash
    const { container } = render(<ConnectedCheckbox {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _connectedcheckboxprops: ConnectedCheckboxProps | undefined = undefined; void _connectedcheckboxprops;
    const _connectedcheckboxref: ConnectedCheckboxRef | undefined = undefined; void _connectedcheckboxref;
    const _connectedcheckboxelement: ConnectedCheckboxElement | undefined = undefined; void _connectedcheckboxelement;
    const _connectedcheckboxcssproperties: ConnectedCheckboxCSSProperties | undefined = undefined; void _connectedcheckboxcssproperties;
    expect(true).toBe(true);
  });
});
