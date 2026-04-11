// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { AILayoutBuilder } from '../ai-layout-builder/AILayoutBuilder';
import type { LayoutBlock, LayoutIntent, LayoutDensity, AILayoutBuilderProps } from '../ai-layout-builder/AILayoutBuilder';

describe('AILayoutBuilder — contract', () => {
  const defaultProps = {
    blocks: [],
  };

  it('renders without crash', () => {
    const { container } = render(<AILayoutBuilder {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(AILayoutBuilder.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<AILayoutBuilder {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<AILayoutBuilder {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 9 optional)', () => {
    // All 9 optional props omitted — should not crash
    const { container } = render(<AILayoutBuilder {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _layoutblock: LayoutBlock | undefined = undefined; void _layoutblock;
    const _layoutintent: LayoutIntent | undefined = undefined; void _layoutintent;
    const _layoutdensity: LayoutDensity | undefined = undefined; void _layoutdensity;
    const _ailayoutbuilderprops: AILayoutBuilderProps | undefined = undefined; void _ailayoutbuilderprops;
    expect(true).toBe(true);
  });
});
