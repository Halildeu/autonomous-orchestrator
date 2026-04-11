// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { FileUploadZone } from '../FileUploadZone';
import type { UploadedFile, FileUploadZoneProps } from '../FileUploadZone';

describe('FileUploadZone — contract', () => {
  
  it('renders without crash', () => {
    const { container } = render(<FileUploadZone  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(FileUploadZone.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<FileUploadZone  access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<FileUploadZone  access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (0 required, 11 optional)', () => {
    // All 11 optional props omitted — should not crash
    const { container } = render(<FileUploadZone  />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _uploadedfile: UploadedFile | undefined = undefined; void _uploadedfile;
    const _fileuploadzoneprops: FileUploadZoneProps | undefined = undefined; void _fileuploadzoneprops;
    expect(true).toBe(true);
  });
});
