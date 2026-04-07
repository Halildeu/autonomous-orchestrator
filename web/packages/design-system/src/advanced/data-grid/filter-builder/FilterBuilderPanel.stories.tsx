import React, { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { FilterBuilderPanel, FilterBuilderButton } from './FilterBuilderPanel';
import type { ColDef, GridApi } from 'ag-grid-community';

const mockColumnDefs: ColDef[] = [
  { field: 'name', headerName: 'Ad', filter: 'agTextColumnFilter' },
  { field: 'department', headerName: 'Departman', filter: 'agSetColumnFilter', filterParams: { values: ['HR', 'Finans', 'IT', 'Operasyon'] } },
  { field: 'salary', headerName: 'Maas', filter: 'agNumberColumnFilter' },
  { field: 'startDate', headerName: 'Baslangic Tarihi', filter: 'agDateColumnFilter' },
];

const createMockGridApi = (): GridApi => {
  const model: Record<string, unknown> = {};
  return {
    getFilterModel: () => model,
    setFilterModel: () => {},
    onFilterChanged: () => {},
    getDisplayedRowCount: () => 42,
    addEventListener: () => {},
    removeEventListener: () => {},
  } as unknown as GridApi;
};

const meta: Meta<typeof FilterBuilderPanel> = {
  title: 'Advanced/DataGrid/FilterBuilder/FilterBuilderPanel',
  component: FilterBuilderPanel,
  parameters: { layout: 'fullscreen' },
};
export default meta;

type Story = StoryObj<typeof FilterBuilderPanel>;

export const Default: Story = {
  render: () => {
    const [open, setOpen] = useState(true);
    const gridApi = createMockGridApi();
    return (
      <div>
        <div style={{ padding: 16 }}>
          <button type="button" onClick={() => setOpen(true)} style={{ padding: '6px 12px', fontSize: 13 }}>
            Filtre Olusturucuyu Ac
          </button>
        </div>
        <FilterBuilderPanel
          gridApi={gridApi}
          columnDefs={mockColumnDefs}
          open={open}
          onClose={() => setOpen(false)}
        />
      </div>
    );
  },
};

export const ToolbarButton: Story = {
  render: () => {
    const gridApi = createMockGridApi();
    return (
      <div style={{ padding: 16 }}>
        <FilterBuilderButton gridApi={gridApi} columnDefs={mockColumnDefs} />
      </div>
    );
  },
};
