import React from 'react';
import { ShellHeader } from '../ShellHeader';
import type { ShellHeaderNavItem } from '../types';

export default {
  title: 'Patterns/ShellHeader',
  component: ShellHeader,
  parameters: { layout: 'fullscreen' },
};

const NAV_ITEMS: ShellHeaderNavItem[] = [
  { key: '/', path: '/', label: 'Ana Sayfa' },
  { key: '/admin', path: '/admin', label: 'Yönetim' },
  { key: '/admin/reports', path: '/admin/reports', label: 'Raporlar' },
  { key: '/settings', path: '/settings', label: 'Ayarlar' },
];

export const Default = () => (
  <ShellHeader
    navItems={NAV_ITEMS}
    currentPath="/admin/reports"
    onNavigate={(path) => console.log('Navigate:', path)}
  />
);

export const WithSlots = () => (
  <ShellHeader
    navItems={NAV_ITEMS}
    currentPath="/"
    onNavigate={(path) => console.log('Navigate:', path)}
    startSlot={<div className="flex items-center gap-2 px-2 text-sm font-bold text-action-primary">Logo</div>}
    endSlot={<div className="flex items-center gap-2 px-2 text-xs text-text-secondary">User Menu</div>}
  />
);

export const EmptyNavigation = () => (
  <ShellHeader
    navItems={[]}
    currentPath="/"
  />
);
