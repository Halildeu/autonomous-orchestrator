import React from 'react';
import { AgGridReact } from 'ag-grid-react';
import type { ColDef } from 'ag-grid-community';
import type { GridMeta, GridColumnDef } from '../types';

type Props = {
  grids: GridMeta[];
  activeGridId: string | null;
  gridData: Record<string, unknown>[];
  onSelectGrid: (gridId: string) => void;
};

const mapColumnType = (col: GridColumnDef): ColDef => {
  const base: ColDef = {
    field: col.field,
    headerName: col.headerName,
    width: col.width,
    sortable: true,
    filter: true,
    resizable: true,
  };
  if (col.type === 'number') {
    base.filter = 'agNumberColumnFilter';
    base.type = 'numericColumn';
  }
  if (col.type === 'badge') {
    base.cellRenderer = (params: { value: unknown }) => {
      const value = String(params.value ?? '');
      const toneClass = badgeTone(value);
      return `<span class="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${toneClass}">${value}</span>`;
    };
  }
  return base;
};

const badgeTone = (value: string): string => {
  const v = value.toUpperCase();
  if (['OK', 'READY', 'PASS', 'YES'].includes(v)) return 'bg-emerald-100 text-emerald-800';
  if (['WARN', 'WARNING', 'MEDIUM'].includes(v)) return 'bg-amber-100 text-amber-800';
  if (['FAIL', 'ERROR', 'NO', 'HIGH', 'BLOCKED'].includes(v)) return 'bg-red-100 text-red-800';
  return 'bg-gray-100 text-gray-700';
};

const GridTabPanel: React.FC<Props> = ({ grids, activeGridId, gridData, onSelectGrid }) => {
  const activeGrid = grids.find((g) => g.gridId === activeGridId);
  const columnDefs = activeGrid ? activeGrid.columns.map(mapColumnType) : [];

  return (
    <div className="space-y-3">
      <div className="flex gap-1 border-b border-border-subtle">
        {grids.map((grid) => (
          <button
            key={grid.gridId}
            onClick={() => onSelectGrid(grid.gridId)}
            className={`px-3 py-2 text-sm font-medium transition-colors ${
              grid.gridId === activeGridId
                ? 'border-b-2 border-action-primary text-action-primary'
                : 'text-text-subtle hover:text-text-primary'
            }`}
          >
            {grid.title}
          </button>
        ))}
      </div>
      <div className="ag-theme-quartz" style={{ width: '100%' }}>
        <AgGridReact
          rowData={gridData}
          columnDefs={columnDefs}
          domLayout="autoHeight"
          pagination
          paginationPageSize={15}
          suppressCellFocus
          animateRows={false}
        />
      </div>
    </div>
  );
};

export default GridTabPanel;
