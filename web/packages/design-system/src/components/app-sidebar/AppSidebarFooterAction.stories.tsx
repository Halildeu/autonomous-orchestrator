import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { AppSidebar } from './AppSidebar';
import { AppSidebarFooterAction } from './AppSidebarFooterAction';

const SettingsIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
  </svg>
);

const HelpIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10" />
    <path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </svg>
);

const meta: Meta<typeof AppSidebarFooterAction> = {
  title: 'Components/Navigation/AppSidebarFooterAction',
  component: AppSidebarFooterAction,
  parameters: { layout: 'fullscreen' },
  decorators: [
    (Story) => (
      <div style={{ height: 300, display: 'flex' }}>
        <AppSidebar>
          <AppSidebar.Footer>
            <Story />
          </AppSidebar.Footer>
        </AppSidebar>
      </div>
    ),
  ],
};
export default meta;

type Story = StoryObj<typeof AppSidebarFooterAction>;

export const Default: Story = {
  args: {
    icon: <SettingsIcon />,
    label: 'Ayarlar',
    onClick: () => {},
  },
};

export const AsLink: Story = {
  args: {
    icon: <HelpIcon />,
    label: 'Yardım',
    href: '#help',
  },
};

export const WithBadge: Story = {
  args: {
    icon: <SettingsIcon />,
    label: 'Bildirimler',
    badge: <span style={{ background: '#ef4444', color: '#fff', borderRadius: 9999, padding: '0 6px', fontSize: 10, fontWeight: 700 }}>3</span>,
    onClick: () => {},
  },
};

export const Disabled: Story = {
  args: {
    icon: <SettingsIcon />,
    label: 'Devre Disi',
    disabled: true,
    onClick: () => {},
  },
};
