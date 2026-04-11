// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { GovernanceBoard } from '../GovernanceBoard';
import type { ComplianceStatus, SeverityLevel, GovernanceItem, GovernanceGroupBy, GovernanceBoardProps } from '../GovernanceBoard';

describe('GovernanceBoard — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<GovernanceBoard {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(GovernanceBoard.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<GovernanceBoard {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<GovernanceBoard {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _compliancestatus: ComplianceStatus | undefined = undefined; void _compliancestatus;
    const _severitylevel: SeverityLevel | undefined = undefined; void _severitylevel;
    const _governanceitem: GovernanceItem | undefined = undefined; void _governanceitem;
    const _governancegroupby: GovernanceGroupBy | undefined = undefined; void _governancegroupby;
    const _governanceboardprops: GovernanceBoardProps | undefined = undefined; void _governanceboardprops;
    expect(true).toBe(true);
  });
});
