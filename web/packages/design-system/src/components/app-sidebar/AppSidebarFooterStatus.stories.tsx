import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { AppSidebar } from './AppSidebar';
import { AppSidebarFooterStatus } from './AppSidebarFooterStatus';

const meta: Meta<typeof AppSidebarFooterStatus> = {
  title: 'Components/Navigation/AppSidebarFooterStatus',
  component: AppSidebarFooterStatus,
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

type Story = StoryObj<typeof AppSidebarFooterStatus>;

export const Default: Story = {
  args: {
    status: 'online',
  },
};

export const AllStatuses: Story = {
  decorators: [
    () => (
      <div style={{ height: 400, display: 'flex' }}>
        <AppSidebar>
          <AppSidebar.Footer>
            <AppSidebarFooterStatus status="online" />
            <AppSidebarFooterStatus status="offline" />
            <AppSidebarFooterStatus status="busy" label="Mesgul" />
            <AppSidebarFooterStatus status="away" label="Uzakta" />
          </AppSidebar.Footer>
        </AppSidebar>
      </div>
    ),
  ],
};

export const WithPulse: Story = {
  args: {
    status: 'online',
    label: 'Aktif',
    pulse: true,
  },
};
