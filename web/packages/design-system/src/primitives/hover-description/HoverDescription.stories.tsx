import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { HoverDescription } from './HoverDescription';

const meta: Meta<typeof HoverDescription> = {
  title: 'Primitives/HoverDescription',
  component: HoverDescription,
  parameters: { layout: 'centered' },
};
export default meta;

type Story = StoryObj<typeof HoverDescription>;

export const Default: Story = {
  render: () => (
    <HoverDescription description="Bu alan toplam geliri ifade eder.">
      <span style={{ textDecoration: 'underline', cursor: 'help' }}>Toplam Gelir</span>
    </HoverDescription>
  ),
};

export const WithTitle: Story = {
  render: () => (
    <HoverDescription
      title="Gelir Detayı"
      description="Bu alan, tüm satış kanallarından elde edilen toplam geliri gösterir. KDV dahil tutardır."
      width={420}
    >
      <span style={{ textDecoration: 'underline', cursor: 'help' }}>Detayları gör</span>
    </HoverDescription>
  ),
};

export const WithDelay: Story = {
  render: () => (
    <HoverDescription
      description="500ms gecikme ile görünür."
      delay={500}
    >
      <span style={{ padding: '4px 8px', border: '1px solid #ccc', borderRadius: 4 }}>
        Gecikmeli tooltip
      </span>
    </HoverDescription>
  ),
};
