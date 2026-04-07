import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { FullscreenToggle } from './FullscreenToggle';

const meta: Meta<typeof FullscreenToggle> = {
  title: 'Primitives/FullscreenToggle',
  component: FullscreenToggle,
  parameters: { layout: 'centered' },
};
export default meta;

type Story = StoryObj<typeof FullscreenToggle>;

export const Default: Story = {
  args: {},
};

export const OutlineVariant: Story = {
  args: {
    variant: 'outline',
    size: 'lg',
  },
};

export const IconOnly: Story = {
  args: {
    showLabel: false,
    size: 'sm',
  },
};
