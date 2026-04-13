// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Result } from '../result/Result';
import type { ResultStatus, ResultProps } from '../result/Result';

describe('Result — contract', () => {
  const defaultProps = {
    status: 'success' as const,
  };

  it('renders without crash', () => {
    const { container } = render(<Result {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Result.displayName).toBeTruthy();
  });

  it('renders with only required props (1 required, 4 optional)', () => {
    // All 4 optional props omitted — should not crash
    const { container } = render(<Result {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _resultstatus: ResultStatus | undefined = undefined; void _resultstatus;
    const _resultprops: ResultProps | undefined = undefined; void _resultprops;
    expect(true).toBe(true);
  });
});
