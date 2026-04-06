import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { DndContext } from '@dnd-kit/core';
import { SortableContext, verticalListSortingStrategy } from '@dnd-kit/sortable';
import { FilterConditionRow } from './FilterConditionRow';
import type { FilterCondition } from './types';
import type { ColDef } from 'ag-grid-community';

const mockColumnDefs: ColDef[] = [
  { field: 'name', headerName: 'Ad', filter: 'agTextColumnFilter' },
  { field: 'age', headerName: 'Yas', filter: 'agNumberColumnFilter' },
  { field: 'date', headerName: 'Tarih', filter: 'agDateColumnFilter' },
];

const baseCondition: FilterCondition = {
  type: 'condition',
  id: 'cond-1',
  colId: 'name',
  filterType: 'text',
  operator: 'contains',
  value: '',
};

const meta: Meta<typeof FilterConditionRow> = {
  title: 'Advanced/DataGrid/FilterBuilder/FilterConditionRow',
  component: FilterConditionRow,
  parameters: { layout: 'padded' },
  decorators: [
    (Story) => (
      <DndContext>
        <SortableContext items={['cond-1']} strategy={verticalListSortingStrategy}>
          <div style={{ maxWidth: 700 }}>
            <Story />
          </div>
        </SortableContext>
      </DndContext>
    ),
  ],
};
export default meta;

type Story = StoryObj<typeof FilterConditionRow>;

const noop = () => {};

export const Default: Story = {
  args: {
    condition: baseCondition,
    columnDefs: mockColumnDefs,
    onUpdate: noop,
    onRemove: noop,
    onMove: noop,
    onClone: noop,
    onToggleLock: noop,
    canRemove: true,
  },
};

export const Locked: Story = {
  args: {
    condition: { ...baseCondition, id: 'cond-locked', locked: true, value: 'test' },
    columnDefs: mockColumnDefs,
    onUpdate: noop,
    onRemove: noop,
    onMove: noop,
    onClone: noop,
    onToggleLock: noop,
    canRemove: true,
  },
};
