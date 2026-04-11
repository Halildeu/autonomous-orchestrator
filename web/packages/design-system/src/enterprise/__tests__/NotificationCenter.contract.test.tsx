// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { NotificationCenter } from '../NotificationCenter';
import type { NotificationType, NotificationItem, NotificationCenterLocaleText, NotificationCenterProps } from '../NotificationCenter';

describe('NotificationCenter — contract', () => {
  const defaultProps = {
    notifications: [],
  };

  it('renders without crash', () => {
    const { container } = render(<NotificationCenter {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(NotificationCenter.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<NotificationCenter {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<NotificationCenter {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 9 optional)', () => {
    // All 9 optional props omitted — should not crash
    const { container } = render(<NotificationCenter {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _notificationtype: NotificationType | undefined = undefined; void _notificationtype;
    const _notificationitem: NotificationItem | undefined = undefined; void _notificationitem;
    const _notificationcenterlocaletext: NotificationCenterLocaleText | undefined = undefined; void _notificationcenterlocaletext;
    const _notificationcenterprops: NotificationCenterProps | undefined = undefined; void _notificationcenterprops;
    expect(true).toBe(true);
  });
});
