import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { GalleryCard } from './GalleryCard';
import type { GalleryItem } from './types';

const meta: Meta<typeof GalleryCard> = {
  title: 'Components/GroupedCardGallery/GalleryCard',
  component: GalleryCard,
  parameters: { layout: 'centered' },
  decorators: [(Story) => <div style={{ width: 280 }}><Story /></div>],
};
export default meta;

type Story = StoryObj<typeof GalleryCard>;

const baseItem: GalleryItem = {
  id: '1',
  title: 'Kullanıcı Raporu',
  group: 'HR',
  description: 'Aktif kullanıcıların detaylı listesi ve departman bazlı dağılımı.',
  icon: '👤',
  tags: ['rapor', 'hr'],
  badge: { label: 'Yeni', tone: 'primary' },
};

export const Default: Story = {
  args: {
    item: baseItem,
    onClick: () => {},
  },
};

export const Minimal: Story = {
  args: {
    item: {
      id: '2',
      title: 'Basit Kart',
      group: 'Genel',
    },
  },
};

export const WithWarningBadge: Story = {
  args: {
    item: {
      ...baseItem,
      id: '3',
      title: 'Kritik Rapor',
      badge: { label: 'Dikkat', tone: 'warning' },
      icon: '⚠️',
    },
    onClick: () => {},
  },
};
