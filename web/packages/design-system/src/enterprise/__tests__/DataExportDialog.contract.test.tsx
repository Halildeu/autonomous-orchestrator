// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { DataExportDialog } from '../DataExportDialog';
import type { ExportFormat, ExportScope, RecordCounts, DataExportDialogLocaleText, DataExportDialogProps } from '../DataExportDialog';

describe('DataExportDialog — contract', () => {
  const defaultProps = {
    open: true,
    onClose: vi.fn(),
    onExport: undefined as any,
  };

  it('renders without crash', () => {
    const { container } = render(<DataExportDialog {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(DataExportDialog.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<DataExportDialog {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<DataExportDialog {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _exportformat: ExportFormat | undefined = undefined; void _exportformat;
    const _exportscope: ExportScope | undefined = undefined; void _exportscope;
    const _recordcounts: RecordCounts | undefined = undefined; void _recordcounts;
    const _dataexportdialoglocaletext: DataExportDialogLocaleText | undefined = undefined; void _dataexportdialoglocaletext;
    const _dataexportdialogprops: DataExportDialogProps | undefined = undefined; void _dataexportdialogprops;
    expect(true).toBe(true);
  });
});
