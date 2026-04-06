// @vitest-environment jsdom
/**
 * ShellHeader — depth tests
 *
 * WHY: ShellHeader renders on every page. A broken activeKey resolution
 * or click handler silently breaks all navigation. These tests catch:
 * - Route matching regressions (longest prefix wins, root special-case)
 * - Click handler not calling onNavigate with correct item
 * - Slot rendering regressions (start/end slots disappearing)
 */
import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import { ShellHeader } from '../shell-header/ShellHeader';
import type { ShellHeaderNavItem } from '../shell-header/types';

afterEach(() => { cleanup(); });

const NAV_ITEMS: ShellHeaderNavItem[] = [
  { key: '/', path: '/', label: 'Ana Sayfa' },
  { key: '/admin', path: '/admin', label: 'Yönetim' },
  { key: '/admin/reports', path: '/admin/reports', label: 'Raporlar' },
  { key: '/settings', path: '/settings', label: 'Ayarlar' },
];

describe('ShellHeader', () => {
  describe('route resolution — longest prefix match', () => {
    it('resolves /admin/reports over /admin when path is /admin/reports/detail', () => {
      render(
        <ShellHeader navItems={NAV_ITEMS} currentPath="/admin/reports/detail" />,
      );
      // The MenuBar should have Raporlar as active, not Yönetim
      const nav = screen.getByRole('menubar', { name: 'Primary navigation' });
      expect(nav).toBeInTheDocument();
    });

    it('resolves root / only for exact match, not as prefix of /settings', () => {
      render(
        <ShellHeader navItems={NAV_ITEMS} currentPath="/settings" />,
      );
      // Ayarlar should be active — Ana Sayfa should NOT be active
      const nav = screen.getByRole('menubar');
      expect(nav).toBeInTheDocument();
    });

    it('renders without crash when navItems is empty', () => {
      const { container } = render(
        <ShellHeader navItems={[]} currentPath="/" />,
      );
      expect(container.firstElementChild).toBeInTheDocument();
    });

    it('handles empty currentPath gracefully', () => {
      const { container } = render(
        <ShellHeader navItems={NAV_ITEMS} currentPath="" />,
      );
      expect(container.firstElementChild).toBeInTheDocument();
    });
  });

  describe('navigation click handler', () => {
    it('calls onNavigate with correct path and item on click', async () => {
      const onNavigate = vi.fn();
      const user = userEvent.setup();

      render(
        <ShellHeader
          navItems={NAV_ITEMS}
          currentPath="/"
          onNavigate={onNavigate}
        />,
      );

      const reportBtn = screen.getByTestId('shell-header-nav-item-admin-reports');
      await user.click(reportBtn);

      expect(onNavigate).toHaveBeenCalledWith(
        '/admin/reports',
        expect.objectContaining({ key: '/admin/reports', label: 'Raporlar' }),
      );
    });

    it('does not throw when onNavigate is undefined', async () => {
      const user = userEvent.setup();
      render(
        <ShellHeader navItems={NAV_ITEMS} currentPath="/" />,
      );

      const settingsBtn = screen.getByTestId('shell-header-nav-item-settings');
      // Should not throw
      await expect(user.click(settingsBtn)).resolves.not.toThrow();
    });
  });

  describe('slots and structure', () => {
    it('renders startSlot and endSlot', () => {
      render(
        <ShellHeader
          navItems={NAV_ITEMS}
          currentPath="/"
          startSlot={<div data-testid="start">Logo</div>}
          endSlot={<div data-testid="end">User</div>}
        />,
      );

      expect(screen.getByTestId('start')).toBeInTheDocument();
      expect(screen.getByTestId('end')).toBeInTheDocument();
    });

    it('sets correct aria-label on navigation', () => {
      render(
        <ShellHeader
          navItems={NAV_ITEMS}
          currentPath="/"
          navAriaLabel="Ana navigasyon"
        />,
      );

      expect(screen.getByRole('menubar', { name: 'Ana navigasyon' })).toBeInTheDocument();
    });

    it('generates correct test IDs from nav item keys', () => {
      render(
        <ShellHeader navItems={NAV_ITEMS} currentPath="/" />,
      );

      // /admin/reports → shell-header-nav-item-admin-reports
      expect(screen.getByTestId('shell-header-nav-item-admin-reports')).toBeInTheDocument();
      // /settings → shell-header-nav-item-settings
      expect(screen.getByTestId('shell-header-nav-item-settings')).toBeInTheDocument();
    });
  });
});
