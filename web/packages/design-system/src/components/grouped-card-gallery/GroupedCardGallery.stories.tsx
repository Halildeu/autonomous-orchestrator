import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { GroupedCardGallery } from './GroupedCardGallery';
import type { GalleryItem } from './types';

const meta: Meta<typeof GroupedCardGallery> = {
  title: 'Components/GroupedCardGallery/GroupedCardGallery',
  component: GroupedCardGallery,
  parameters: { layout: 'padded' },
};
export default meta;

type Story = StoryObj<typeof GroupedCardGallery>;

const sampleItems: GalleryItem[] = [
  { id: '1', title: 'Gelir Tablosu', group: 'Finans', description: 'Aylik gelir ozeti', icon: '📊', tags: ['finans', 'rapor'] },
  { id: '2', title: 'Bilanço', group: 'Finans', description: 'Varlık ve yükümlülükler', icon: '📋', tags: ['finans'] },
  { id: '3', title: 'Bordro Raporu', group: 'HR', description: 'Calisan maas detaylari', icon: '👤', tags: ['hr', 'bordro'] },
  { id: '4', title: 'İzin Takibi', group: 'HR', description: 'Yillik izin durumu', icon: '📅', tags: ['hr', 'izin'] },
  { id: '5', title: 'Stok Durumu', group: 'Operasyon', description: 'Depo stok seviyeleri', icon: '📦', tags: ['stok'] },
  { id: '6', title: 'Siparis Takibi', group: 'Operasyon', description: 'Acik siparisler', icon: '🚚', tags: ['siparis'], badge: { label: 'Yeni', tone: 'primary' } },
];

export const Default: Story = {
  args: {
    items: sampleItems,
    groupBy: 'group',
    searchPlaceholder: 'Rapor ara...',
    defaultExpandedGroups: ['Finans', 'HR'],
    onItemClick: (item: GalleryItem) => console.log('clicked', item.id),
  },
};

export const CustomGroupOrder: Story = {
  args: {
    items: sampleItems,
    groupBy: 'group',
    searchPlaceholder: 'Ara...',
    groupOrder: ['Operasyon', 'Finans', 'HR'],
    defaultExpandedGroups: ['Operasyon'],
    columns: { sm: 1, md: 2, lg: 2, xl: 3 },
  },
};
