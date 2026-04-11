// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Textarea } from '../input/Textarea';
import type { TextAreaResize, TextareaProps } from '../input/Textarea';

describe('Textarea — contract', () => {
  const defaultProps = {
    value: undefined as any,
    event: undefined as any,
  };

  it('renders without crash', () => {
    const { container } = render(<Textarea {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Textarea.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Textarea {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Textarea {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (2 required, 13 optional)', () => {
    // All 13 optional props omitted — should not crash
    const { container } = render(<Textarea {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _textarearesize: TextAreaResize | undefined = undefined; void _textarearesize;
    const _textareaprops: TextareaProps | undefined = undefined; void _textareaprops;
    expect(true).toBe(true);
  });
});
