import React, { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { GalleryGroup } from './GalleryGroup';

const meta: Meta<typeof GalleryGroup> = {
  title: 'Components/GroupedCardGallery/GalleryGroup',
  component: GalleryGroup,
  parameters: { layout: 'padded' },
};
export default meta;

type Story = StoryObj<typeof GalleryGroup>;

const SampleContent = () => (
  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
    {['Rapor A', 'Rapor B', 'Rapor C'].map((name) => (
      <div key={name} style={{ padding: 12, border: '1px solid #e5e5e5', borderRadius: 8, fontSize: 13 }}>
        {name}
      </div>
    ))}
  </div>
);

export const Default: Story = {
  render: () => {
    const [expanded, setExpanded] = useState(true);
    return (
      <GalleryGroup name="Finans" count={3} expanded={expanded} onToggle={() => setExpanded(!expanded)}>
        <SampleContent />
      </GalleryGroup>
    );
  },
};

export const Collapsed: Story = {
  render: () => {
    const [expanded, setExpanded] = useState(false);
    return (
      <GalleryGroup name="HR" count={5} expanded={expanded} onToggle={() => setExpanded(!expanded)}>
        <SampleContent />
      </GalleryGroup>
    );
  },
};
