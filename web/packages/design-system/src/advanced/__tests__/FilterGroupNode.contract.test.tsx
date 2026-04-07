// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import React from 'react';
import { DndContext } from '@dnd-kit/core';
import { FilterGroupNode } from '../data-grid/filter-builder/FilterGroupNode';
import type { FilterGroup } from '../data-grid/filter-builder/types';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const defaultColumnDefs = [
  { field: 'name', headerName: 'Name', filter: 'agTextColumnFilter' },
];

function createRootGroup(overrides: Partial<FilterGroup> = {}): FilterGroup {
  return {
    type: 'group',
    id: 'root',
    logic: 'AND',
    children: [],
    ...overrides,
  };
}

function createDefaultProps(groupOverrides: Partial<FilterGroup> = {}, propOverrides: Record<string, unknown> = {}) {
  return {
    group: createRootGroup(groupOverrides),
    columnDefs: defaultColumnDefs,
    depth: 0,
    isRoot: true,
    maxDepthReached: false,
    onAddCondition: vi.fn(),
    onAddGroup: vi.fn(),
    onRemoveNode: vi.fn(),
    onUpdateCondition: vi.fn(),
    onSetLogic: vi.fn(),
    onMoveNode: vi.fn(),
    onCloneNode: vi.fn(),
    onToggleLock: vi.fn(),
    onToggleNot: vi.fn(),
    ...propOverrides,
  };
}

function renderGroupNode(groupOverrides: Partial<FilterGroup> = {}, propOverrides: Record<string, unknown> = {}) {
  const props = createDefaultProps(groupOverrides, propOverrides);
  return {
    ...render(
      <DndContext>
        <FilterGroupNode {...props} />
      </DndContext>,
    ),
    props,
  };
}

describe('FilterGroupNode — contract', () => {
  it('renders empty state when group has no children', () => {
    renderGroupNode();
    expect(screen.getByText('Henüz kural eklenmedi')).toBeInTheDocument();
  });

  it('calls onAddCondition with group id when "+ Kural" clicked', async () => {
    const user = userEvent.setup();
    const { props } = renderGroupNode();

    const addRuleBtn = screen.getByText('Kural');
    await user.click(addRuleBtn);
    expect(props.onAddCondition).toHaveBeenCalledWith('root');
  });

  it('calls onAddGroup with group id when "+ Grup" clicked', async () => {
    const user = userEvent.setup();
    const { props } = renderGroupNode();

    const addGroupBtn = screen.getByText('Grup');
    await user.click(addGroupBtn);
    expect(props.onAddGroup).toHaveBeenCalledWith('root');
  });

  it('hides "+ Grup" button when maxDepthReached is true', () => {
    renderGroupNode({}, { maxDepthReached: true });
    expect(screen.queryByText('Grup')).not.toBeInTheDocument();
  });

  it('calls onToggleNot when NOT toggle clicked', async () => {
    const user = userEvent.setup();
    const { props } = renderGroupNode();

    // The NOT button shows "DEĞİL" in Turkish
    const notBtn = screen.getByText('DEĞİL');
    await user.click(notBtn);
    expect(props.onToggleNot).toHaveBeenCalledWith('root');
  });

  it('disables action buttons when group is locked', () => {
    renderGroupNode({ locked: true });

    const addRuleBtn = screen.getByText('Kural').closest('button');
    expect(addRuleBtn).toBeDisabled();
  });

  it('hides delete and clone buttons for root group', () => {
    renderGroupNode({}, { isRoot: true });

    expect(screen.queryByTitle('Grubu sil')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Grubu kopyala')).not.toBeInTheDocument();
  });

  it('shows delete and clone buttons for non-root group', () => {
    renderGroupNode({}, { isRoot: false });

    expect(screen.getByTitle('Grubu sil')).toBeInTheDocument();
    expect(screen.getByTitle('Grubu kopyala')).toBeInTheDocument();
  });

  it('renders child conditions inside sortable context', () => {
    const group = createRootGroup({
      children: [
        { type: 'condition', id: 'c1', colId: 'name', filterType: 'text', operator: 'contains', value: 'test' },
      ],
    });

    render(
      <DndContext>
        <FilterGroupNode {...createDefaultProps({ children: group.children })} />
      </DndContext>,
    );

    // Condition row should render (has column selector)
    const selects = screen.getAllByRole('combobox');
    expect(selects.length).toBeGreaterThanOrEqual(1);
  });
});
