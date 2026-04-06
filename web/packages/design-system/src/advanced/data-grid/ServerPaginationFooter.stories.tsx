import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { ServerPaginationFooter } from './ServerPaginationFooter';
import type { GridApi } from 'ag-grid-community';

const createMockGridApi = (overrides: {
  currentPage?: number;
  totalPages?: number;
  pageSize?: number;
  rowCount?: number;
} = {}): GridApi => {
  const { currentPage = 0, totalPages = 10, pageSize = 50, rowCount = 487 } = overrides;
  return {
    paginationGetCurrentPage: () => currentPage,
    paginationGetTotalPages: () => totalPages,
    paginationGetPageSize: () => pageSize,
    paginationGetRowCount: () => rowCount,
    paginationGoToPage: () => {},
    setGridOption: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
  } as unknown as GridApi;
};

const meta: Meta<typeof ServerPaginationFooter> = {
  title: 'Advanced/DataGrid/ServerPaginationFooter',
  component: ServerPaginationFooter,
  parameters: { layout: 'padded' },
  decorators: [(Story) => <div style={{ border: '1px solid #e5e5e5', borderRadius: 8 }}><Story /></div>],
};
export default meta;

type Story = StoryObj<typeof ServerPaginationFooter>;

export const Default: Story = {
  args: {
    gridApi: createMockGridApi(),
  },
};

export const WithStartSlot: Story = {
  args: {
    gridApi: createMockGridApi({ currentPage: 2, totalPages: 20, rowCount: 980 }),
    startSlot: <span style={{ fontSize: 11, opacity: 0.7 }}>Sunucu modu</span>,
  },
};

export const LastPage: Story = {
  args: {
    gridApi: createMockGridApi({ currentPage: 9, totalPages: 10, rowCount: 487 }),
  },
};

export const EmptyData: Story = {
  args: {
    gridApi: createMockGridApi({ currentPage: 0, totalPages: 0, pageSize: 50, rowCount: 0 }),
  },
};
