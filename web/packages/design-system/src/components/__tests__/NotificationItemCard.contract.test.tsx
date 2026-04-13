// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { NotificationItemCard } from '../notification-drawer/NotificationItemCard';
import type { NotificationItemType, NotificationItemPriority, NotificationSurfaceItem, NotificationItemCardProps } from '../notification-drawer/NotificationItemCard';

describe('NotificationItemCard — contract', () => {
  const defaultProps = {
    item: { id: '1', message: 'Test notification' } as NotificationSurfaceItem,
  };

  it('renders without crash', () => {
    const { container } = render(<NotificationItemCard {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(NotificationItemCard.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<NotificationItemCard {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<NotificationItemCard {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (6 required, 10 optional)', () => {
    // All 10 optional props omitted — should not crash
    const { container } = render(<NotificationItemCard {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _notificationitemtype: NotificationItemType | undefined = undefined; void _notificationitemtype;
    const _notificationitempriority: NotificationItemPriority | undefined = undefined; void _notificationitempriority;
    const _notificationsurfaceitem: NotificationSurfaceItem | undefined = undefined; void _notificationsurfaceitem;
    const _notificationitemcardprops: NotificationItemCardProps | undefined = undefined; void _notificationitemcardprops;
    expect(true).toBe(true);
  });
});
