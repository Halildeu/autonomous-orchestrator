// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { NotificationPanel } from '../notification-drawer/NotificationPanel';
import type { NotificationPanelFilter, NotificationPanelGrouping, NotificationPanelDateGrouping, NotificationPanelProps } from '../notification-drawer/NotificationPanel';

describe('NotificationPanel — contract', () => {
  const defaultProps = {
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<NotificationPanel {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(NotificationPanel.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<NotificationPanel {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<NotificationPanel {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 39 optional)', () => {
    // All 39 optional props omitted — should not crash
    const { container } = render(<NotificationPanel {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _notificationpanelfilter: NotificationPanelFilter | undefined = undefined; void _notificationpanelfilter;
    const _notificationpanelgrouping: NotificationPanelGrouping | undefined = undefined; void _notificationpanelgrouping;
    const _notificationpaneldategrouping: NotificationPanelDateGrouping | undefined = undefined; void _notificationpaneldategrouping;
    const _notificationpanelprops: NotificationPanelProps | undefined = undefined; void _notificationpanelprops;
    expect(true).toBe(true);
  });
});
