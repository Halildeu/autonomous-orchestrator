// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ConnectedTextarea } from '../connected/ConnectedTextarea';
import type { ConnectedTextareaProps, ConnectedTextareaRef, ConnectedTextareaElement, ConnectedTextareaCSSProperties } from '../connected/ConnectedTextarea';

describe('ConnectedTextarea — contract', () => {
  const defaultProps = {
    name: 'test',
  };

  it('renders without crash', () => {
    const { container } = render(<ConnectedTextarea {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(ConnectedTextarea.displayName).toBeTruthy();
  });

  it('renders with only required props (1 required, 6 optional)', () => {
    // All 6 optional props omitted — should not crash
    const { container } = render(<ConnectedTextarea {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _connectedtextareaprops: ConnectedTextareaProps | undefined = undefined; void _connectedtextareaprops;
    const _connectedtextarearef: ConnectedTextareaRef | undefined = undefined; void _connectedtextarearef;
    const _connectedtextareaelement: ConnectedTextareaElement | undefined = undefined; void _connectedtextareaelement;
    const _connectedtextareacssproperties: ConnectedTextareaCSSProperties | undefined = undefined; void _connectedtextareacssproperties;
    expect(true).toBe(true);
  });
});
