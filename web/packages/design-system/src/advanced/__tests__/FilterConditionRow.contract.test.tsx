// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { DndContext } from '@dnd-kit/core';
import { SortableContext } from '@dnd-kit/sortable';
import { FilterConditionRow } from '../data-grid/filter-builder/FilterConditionRow';
import type { FilterCondition } from '../data-grid/filter-builder/types';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const defaultColumnDefs = [
  { field: 'name', headerName: 'Name', filter: 'agTextColumnFilter' },
  { field: 'age', headerName: 'Age', filter: 'agNumberColumnFilter' },
  { field: 'status', headerName: 'Status', filter: 'agSetColumnFilter', filterParams: { values: ['Active', 'Inactive'] } },
];

function createCondition(overrides: Partial<FilterCondition> = {}): FilterCondition {
  return {
    type: 'condition',
    id: 'cond-1',
    colId: 'name',
    filterType: 'text',
    operator: 'contains',
    value: '',
    ...overrides,
  };
}

function renderConditionRow(
  conditionOverrides: Partial<FilterCondition> = {},
  propOverrides: Record<string, unknown> = {},
) {
  const condition = createCondition(conditionOverrides);
  const props = {
    condition,
    columnDefs: defaultColumnDefs,
    onUpdate: vi.fn(),
    onRemove: vi.fn(),
    onMove: vi.fn(),
    onClone: vi.fn(),
    onToggleLock: vi.fn(),
    canRemove: true,
    ...propOverrides,
  };

  return {
    ...render(
      <DndContext>
        <SortableContext items={[condition.id]}>
          <FilterConditionRow {...props} />
        </SortableContext>
      </DndContext>,
    ),
    props,
  };
}

describe('FilterConditionRow — contract', () => {
  it('renders column selector with filterable columns', () => {
    renderConditionRow();

    const select = screen.getAllByRole('combobox')[0];
    expect(select).toBeInTheDocument();
    // Should have "Name", "Age", "Status" options plus placeholder
    expect(select.querySelectorAll('option').length).toBeGreaterThanOrEqual(3);
  });

  it('calls onUpdate with cascading reset when column changes', async () => {
    const user = userEvent.setup();
    const { props } = renderConditionRow({ colId: 'name', filterType: 'text' });

    const columnSelect = screen.getAllByRole('combobox')[0];
    await user.selectOptions(columnSelect, 'age');

    expect(props.onUpdate).toHaveBeenCalledWith('cond-1', expect.objectContaining({
      colId: 'age',
      filterType: 'number',
    }));
  });

  it('disables inputs when condition is locked', () => {
    renderConditionRow({ locked: true });

    const selects = screen.getAllByRole('combobox');
    for (const select of selects) {
      expect(select).toBeDisabled();
    }
  });

  it('disables inputs when parentLocked is true', () => {
    renderConditionRow({}, { parentLocked: true });

    const selects = screen.getAllByRole('combobox');
    for (const select of selects) {
      expect(select).toBeDisabled();
    }
  });

  it('calls onRemove when delete button clicked', async () => {
    const user = userEvent.setup();
    const { props } = renderConditionRow();

    const deleteBtn = screen.getByTitle('Koşulu sil');
    await user.click(deleteBtn);
    expect(props.onRemove).toHaveBeenCalledWith('cond-1');
  });

  it('hides delete button when canRemove is false', () => {
    renderConditionRow({}, { canRemove: false });
    expect(screen.queryByTitle('Koşulu sil')).not.toBeInTheDocument();
  });

  it('calls onClone when clone button clicked', async () => {
    const user = userEvent.setup();
    const { props } = renderConditionRow();

    const cloneBtn = screen.getByTitle('Kopyala');
    await user.click(cloneBtn);
    expect(props.onClone).toHaveBeenCalledWith('cond-1');
  });

  it('calls onMove with direction when move buttons clicked', async () => {
    const user = userEvent.setup();
    const { props } = renderConditionRow();

    const upBtn = screen.getByTitle('Yukarı taşı');
    await user.click(upBtn);
    expect(props.onMove).toHaveBeenCalledWith('cond-1', 'up');

    const downBtn = screen.getByTitle('Aşağı taşı');
    await user.click(downBtn);
    expect(props.onMove).toHaveBeenCalledWith('cond-1', 'down');
  });

  it('calls onToggleLock when lock button clicked', async () => {
    const user = userEvent.setup();
    const { props } = renderConditionRow();

    const lockBtn = screen.getByTitle('Kilitle');
    await user.click(lockBtn);
    expect(props.onToggleLock).toHaveBeenCalledWith('cond-1');
  });
});
