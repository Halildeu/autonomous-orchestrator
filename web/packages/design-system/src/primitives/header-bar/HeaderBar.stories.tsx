import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { HeaderBar } from './HeaderBar';

const meta: Meta<typeof HeaderBar> = {
  title: 'Primitives/HeaderBar',
  component: HeaderBar,
  parameters: { layout: 'fullscreen' },
};
export default meta;

type Story = StoryObj<typeof HeaderBar>;

export const Default: Story = {
  render: () => (
    <div>
      <HeaderBar>
        <span style={{ fontWeight: 600, fontSize: 14 }}>Logo</span>
        <nav style={{ display: 'flex', gap: 12, fontSize: 13 }}>
          <a href="#">Ana Sayfa</a>
          <a href="#">Raporlar</a>
          <a href="#">Ayarlar</a>
        </nav>
      </HeaderBar>
      <div style={{ paddingTop: 80, padding: 24 }}>
        <p>Page content below the header bar.</p>
      </div>
    </div>
  ),
};

export const WithoutCard: Story = {
  render: () => (
    <div>
      <HeaderBar card={false} blur={false}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
          <span style={{ fontWeight: 600, fontSize: 14 }}>Plain Header</span>
          <span style={{ fontSize: 12, opacity: 0.6 }}>No card styling</span>
        </div>
      </HeaderBar>
      <div style={{ paddingTop: 80, padding: 24 }}>
        <p>Page content below the header bar.</p>
      </div>
    </div>
  ),
};
