import React, { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { GallerySearchBar } from './GallerySearchBar';

const meta: Meta<typeof GallerySearchBar> = {
  title: 'Components/GroupedCardGallery/GallerySearchBar',
  component: GallerySearchBar,
  parameters: { layout: 'centered' },
  decorators: [(Story) => <div style={{ width: 400 }}><Story /></div>],
};
export default meta;

type Story = StoryObj<typeof GallerySearchBar>;

export const Default: Story = {
  render: () => {
    const [value, setValue] = useState('');
    return (
      <GallerySearchBar
        value={value}
        onChange={setValue}
        placeholder="Rapor ara..."
        summary="12 rapor"
      />
    );
  },
};

export const WithValue: Story = {
  render: () => {
    const [value, setValue] = useState('finans');
    return (
      <GallerySearchBar
        value={value}
        onChange={setValue}
        placeholder="Rapor ara..."
        summary="3 / 12 sonuc"
      />
    );
  },
};
