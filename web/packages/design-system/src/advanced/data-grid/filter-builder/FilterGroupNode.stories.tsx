import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { DndContext } from '@dnd-kit/core';
import { FilterGroupNode } from './FilterGroupNode';
import type { FilterGroup } from './types';
import type { ColDef } from 'ag-grid-community';

const mockColumnDefs: ColDef[] = [
  { field: 'name', headerName: 'Ad', filter: 'agTextColumnFilter' },
  { field: 'amount', headerName: 'Tutar', filter: 'agNumberColumnFilter' },
  { field: 'date', headerName: 'Tarih', filter: 'agDateColumnFilter' },
];

const sampleGroup: FilterGroup = {
  type: 'group',
  id: 'root',
  logic: 'AND',
  children: [
    { type: 'condition', id: 'c1', colId: 'name', filterType: 'text', operator: 'contains', value: 'test' },
    { type: 'combinator', id: 'cb1', logic: 'AND' },
    { type: 'condition', id: 'c2', colId: 'amount', filterType: 'number', operator: 'greaterThan', value: 100 },
  ],
};

const emptyGroup: FilterGroup = {
  type: 'group',
  id: 'empty-root',
  logic: 'AND',
  children: [],
};

const noop = () => {};

const meta: Meta<typeof FilterGroupNode> = {
  title: 'Advanced/DataGrid/FilterBuilder/FilterGroupNode',
  component: FilterGroupNode,
  parameters: { layout: 'padded' },
  decorators: [
    (Story) => (
      <DndContext>
        <div style={{ maxWidth: 700 }}>
          <Story />
        </div>
      </DndContext>
    ),
  ],
};
export default meta;

type Story = StoryObj<typeof FilterGroupNode>;

export const Default: Story = {
  args: {
    group: sampleGroup,
    columnDefs: mockColumnDefs,
    depth: 0,
    isRoot: true,
    maxDepthReached: false,
    onAddCondition: noop,
    onAddGroup: noop,
    onRemoveNode: noop,
    onUpdateCondition: noop,
    onSetLogic: noop,
    onMoveNode: noop,
    onCloneNode: noop,
    onToggleLock: noop,
    onToggleNot: noop,
  },
};

export const EmptyState: Story = {
  args: {
    group: emptyGroup,
    columnDefs: mockColumnDefs,
    depth: 0,
    isRoot: true,
    maxDepthReached: false,
    onAddCondition: noop,
    onAddGroup: noop,
    onRemoveNode: noop,
    onUpdateCondition: noop,
    onSetLogic: noop,
    onMoveNode: noop,
    onCloneNode: noop,
    onToggleLock: noop,
    onToggleNot: noop,
  },
};
