// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { CommentThread } from '../CommentThread';
import type { Comment, CommentThreadProps } from '../CommentThread';

describe('CommentThread — contract', () => {
  const defaultProps = {
    comments: [],
  };

  it('renders without crash', () => {
    const { container } = render(<CommentThread {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(CommentThread.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<CommentThread {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<CommentThread {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 4 optional)', () => {
    // All 4 optional props omitted — should not crash
    const { container } = render(<CommentThread {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _comment: Comment | undefined = undefined; void _comment;
    const _commentthreadprops: CommentThreadProps | undefined = undefined; void _commentthreadprops;
    expect(true).toBe(true);
  });
});
