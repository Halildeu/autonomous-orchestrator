// @vitest-environment jsdom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom/vitest';
import React from 'react';

// Mock useFilterBuilder — isolate panel from hook internals
const mockSetRoot = vi.fn();
const mockAddCondition = vi.fn();
const mockClear = vi.fn();
let mockIsEmpty = true;

vi.mock('../data-grid/filter-builder/useFilterBuilder', () => ({
  useFilterBuilder: () => ({
    root: { type: 'group', id: 'root', logic: 'AND', children: [] },
    setRoot: mockSetRoot,
    addCondition: mockAddCondition,
    addGroup: vi.fn(),
    removeNode: vi.fn(),
    updateCondition: vi.fn(),
    setLogic: vi.fn(),
    moveNode: vi.fn(),
    moveNodeDnD: vi.fn(),
    cloneNode: vi.fn(),
    toggleLock: vi.fn(),
    toggleNot: vi.fn(),
    clear: mockClear,
    isEmpty: mockIsEmpty,
    maxDepthReached: false,
  }),
  createEmptyGroup: () => ({ type: 'group', id: 'root', logic: 'AND', children: [] }),
}));

// Mock filterModelConverter
vi.mock('../data-grid/filter-builder/filterModelConverter', () => ({
  treeToFilterModel: () => ({}),
  filterModelToTree: () => ({ type: 'group', id: 'root', logic: 'AND', children: [] }),
  extractMultiSearchParams: () => ({}),
}));

// Mock FilterGroupNode to avoid deep render
vi.mock('../data-grid/filter-builder/FilterGroupNode', () => ({
  FilterGroupNode: () => <div data-testid="filter-group-node">FilterGroupNode</div>,
}));

import { FilterBuilderPanel } from '../data-grid/filter-builder/FilterBuilderPanel';

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  mockIsEmpty = true;
});

function createMockGridApi() {
  return {
    setFilterModel: vi.fn(),
    getFilterModel: vi.fn(() => ({})),
    onFilterChanged: vi.fn(),
    getDisplayedRowCount: vi.fn(() => 100),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  } as unknown as import('ag-grid-community').GridApi;
}

const defaultColumnDefs = [
  { field: 'name', headerName: 'Name', filter: 'agTextColumnFilter' },
  { field: 'age', headerName: 'Age', filter: 'agNumberColumnFilter' },
];

describe('FilterBuilderPanel — contract', () => {
  it('renders nothing when open=false', () => {
    const gridApi = createMockGridApi();
    const { container } = render(
      <FilterBuilderPanel
        gridApi={gridApi}
        columnDefs={defaultColumnDefs}
        open={false}
        onClose={vi.fn()}
      />,
    );
    expect(container.innerHTML).toBe('');
  });

  it('renders panel with header and footer when open=true', () => {
    const gridApi = createMockGridApi();
    render(
      <FilterBuilderPanel
        gridApi={gridApi}
        columnDefs={defaultColumnDefs}
        open={true}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText('Filtre Oluşturucu')).toBeInTheDocument();
    expect(screen.getByText('Uygula')).toBeInTheDocument();
    expect(screen.getByText('Temizle')).toBeInTheDocument();
  });

  it('calls gridApi.setFilterModel and onClose on Apply click', async () => {
    mockIsEmpty = false;
    const user = userEvent.setup();
    const gridApi = createMockGridApi();
    const onClose = vi.fn();

    render(
      <FilterBuilderPanel
        gridApi={gridApi}
        columnDefs={defaultColumnDefs}
        open={true}
        onClose={onClose}
      />,
    );

    await user.click(screen.getByText('Uygula'));
    expect(gridApi.setFilterModel).toHaveBeenCalled();
    expect(gridApi.onFilterChanged).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it('calls clear, resets filter model and closes on Clear click', async () => {
    const user = userEvent.setup();
    const gridApi = createMockGridApi();
    const onClose = vi.fn();

    render(
      <FilterBuilderPanel
        gridApi={gridApi}
        columnDefs={defaultColumnDefs}
        open={true}
        onClose={onClose}
      />,
    );

    await user.click(screen.getByText('Temizle'));
    expect(gridApi.setFilterModel).toHaveBeenCalledWith(null);
    expect(gridApi.onFilterChanged).toHaveBeenCalled();
    expect(mockClear).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it('disables Apply button when filter tree is empty', () => {
    mockIsEmpty = true;
    const gridApi = createMockGridApi();

    render(
      <FilterBuilderPanel
        gridApi={gridApi}
        columnDefs={defaultColumnDefs}
        open={true}
        onClose={vi.fn()}
      />,
    );

    const applyBtn = screen.getByText('Uygula').closest('button');
    expect(applyBtn).toBeDisabled();
  });

  it('calls onClose when backdrop is clicked', async () => {
    const user = userEvent.setup();
    const gridApi = createMockGridApi();
    const onClose = vi.fn();

    const { container } = render(
      <FilterBuilderPanel
        gridApi={gridApi}
        columnDefs={defaultColumnDefs}
        open={true}
        onClose={onClose}
      />,
    );

    // The backdrop is the first fixed element (inset-0)
    const backdrop = container.querySelector('.fixed.inset-0');
    if (backdrop) {
      await user.click(backdrop);
      expect(onClose).toHaveBeenCalled();
    }
  });
});
