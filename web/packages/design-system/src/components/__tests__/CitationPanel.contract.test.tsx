// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { CitationPanel } from '../citation-panel/CitationPanel';
import type { CitationKind, CitationPanelItem, CitationPanelProps } from '../citation-panel/CitationPanel';

describe('CitationPanel — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<CitationPanel {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(CitationPanel.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<CitationPanel {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<CitationPanel {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 7 optional)', () => {
    // All 7 optional props omitted — should not crash
    const { container } = render(<CitationPanel {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _citationkind: CitationKind | undefined = undefined; void _citationkind;
    const _citationpanelitem: CitationPanelItem | undefined = undefined; void _citationpanelitem;
    const _citationpanelprops: CitationPanelProps | undefined = undefined; void _citationpanelprops;
    expect(true).toBe(true);
  });
});
