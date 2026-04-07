import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { StatusIndicator } from './StatusIndicator';

const meta: Meta<typeof StatusIndicator> = {
  title: 'Primitives/StatusIndicator',
  component: StatusIndicator,
  parameters: { layout: 'centered' },
};
export default meta;

type Story = StoryObj<typeof StatusIndicator>;

export const Default: Story = {
  args: {
    status: 'online',
    label: 'Online',
  },
};

export const AllStatuses: Story = {
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <StatusIndicator status="online" label="Online" />
      <StatusIndicator status="offline" label="Offline" />
      <StatusIndicator status="busy" label="Busy" />
      <StatusIndicator status="away" label="Away" />
      <StatusIndicator status="unknown" label="Unknown" />
    </div>
  ),
};

export const WithPulse: Story = {
  args: {
    status: 'online',
    label: 'Active',
    pulse: true,
    size: 'lg',
  },
};

export const DotOnly: Story = {
  args: {
    status: 'busy',
    showLabel: false,
  },
};
