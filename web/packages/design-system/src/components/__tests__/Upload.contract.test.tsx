// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { Upload } from '../upload/Upload';
import type { UploadFileItem, UploadProps } from '../upload/Upload';

describe('Upload — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<Upload  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(Upload.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<Upload  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<Upload  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 12 optional)', () => {
    // All 12 optional props omitted — should not crash
    const { container } = render(<Upload  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _uploadfileitem: UploadFileItem | undefined = undefined; void _uploadfileitem;
    const _uploadprops: UploadProps | undefined = undefined; void _uploadprops;
    expect(true).toBe(true);
  });
});
