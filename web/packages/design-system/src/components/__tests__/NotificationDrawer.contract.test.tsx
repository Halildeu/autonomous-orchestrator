// @vitest-environment jsdom
// Auto-generated contract test — do not edit manually
// Regenerate with: node scripts/ci/generate-contract-tests.mjs --write
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { NotificationDrawer } from '../notification-drawer/NotificationDrawer';
import type { NotificationDrawerProps, NotificationDrawerRef, NotificationDrawerElement, NotificationDrawerCSSProperties } from '../notification-drawer/NotificationDrawer';

describe('NotificationDrawer — contract', () => {
  const defaultProps = {
    open: true,
    disablePortal: true,
    onClose: vi.fn(),
    items: [],
  };

  it('renders without crash', () => {
    const { container } = render(<NotificationDrawer {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('has displayName', () => {
    expect(NotificationDrawer.displayName).toBeTruthy();
  });

  it('respects access=hidden', () => {
    const { container } = render(<NotificationDrawer {...defaultProps} access="hidden" />);
    expect(container.innerHTML).toBe('');
  });

  it('applies disabled state via access=readonly', () => {
    const { container } = render(<NotificationDrawer {...defaultProps} access="readonly" />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('renders with only required props (1 required, 11 optional)', () => {
    // disablePortal needed to render inline
    const { container } = render(<NotificationDrawer {...defaultProps} />);
    expect(container.firstElementChild).toBeTruthy();
  });

  it('exports expected types', () => {
    // Type-level check — if this compiles, types are exported correctly
    const _notificationdrawerprops: NotificationDrawerProps | undefined = undefined; void _notificationdrawerprops;
    const _notificationdrawerref: NotificationDrawerRef | undefined = undefined; void _notificationdrawerref;
    const _notificationdrawerelement: NotificationDrawerElement | undefined = undefined; void _notificationdrawerelement;
    const _notificationdrawercssproperties: NotificationDrawerCSSProperties | undefined = undefined; void _notificationdrawercssproperties;
    expect(true).toBe(true);
  });
});
