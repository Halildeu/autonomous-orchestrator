// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { JsonViewer } from '../json-viewer/JsonViewer';
import type { JsonViewerProps, JsonViewerRef, JsonViewerElement, JsonViewerCSSProperties } from '../json-viewer/JsonViewer';

describe('JsonViewer — contract', () => {
  const defaultProps = {
    value: undefined as any,
  };

  it('renders without crash', () => {
    const { container } = render(<JsonViewer {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(JsonViewer.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<JsonViewer {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<JsonViewer {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 19 optional)', () => {
    // All 19 optional props omitted — should not crash
    const { container } = render(<JsonViewer {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _jsonviewerprops: JsonViewerProps | undefined = undefined; void _jsonviewerprops;
    const _jsonviewerref: JsonViewerRef | undefined = undefined; void _jsonviewerref;
    const _jsonviewerelement: JsonViewerElement | undefined = undefined; void _jsonviewerelement;
    const _jsonviewercssproperties: JsonViewerCSSProperties | undefined = undefined; void _jsonviewercssproperties;
    expect(true).toBe(true);
  });
});
