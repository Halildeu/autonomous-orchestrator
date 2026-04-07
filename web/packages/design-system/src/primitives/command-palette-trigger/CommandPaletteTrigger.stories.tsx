import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { CommandPaletteTrigger } from './CommandPaletteTrigger';

const meta: Meta<typeof CommandPaletteTrigger> = {
  title: 'Primitives/CommandPaletteTrigger',
  component: CommandPaletteTrigger,
  parameters: { layout: 'centered' },
  decorators: [(Story) => <div style={{ width: 320 }}><Story /></div>],
};
export default meta;

type Story = StoryObj<typeof CommandPaletteTrigger>;

export const Default: Story = {
  args: {
    placeholder: 'Ara...',
    shortcut: 'Ctrl+K',
  },
};

export const Compact: Story = {
  args: {
    compact: true,
  },
  decorators: [(Story) => <div style={{ width: 48 }}><Story /></div>],
};

export const WithoutShortcut: Story = {
  args: {
    placeholder: 'Komut ara...',
  },
};
