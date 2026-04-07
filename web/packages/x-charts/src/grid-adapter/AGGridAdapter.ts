/**
 * AGGridAdapter — AG Grid implementation of GridAdapter
 *
 * Wraps AG Grid API to provide a vendor-neutral interface for
 * chart ↔ grid integration. Translates between AG Grid's filter/sort
 * models and the GridAdapter contract.
 *
 * @see GridAdapter interface (types.ts)
 * @see AG Grid API docs
 */

import type {
  GridAdapter,
  GridColumnDef,
  GridFilterEntry,
  GridSortEntry,
  GridSelectionEvent,
  FilterOperator,
} from './types';

/* ------------------------------------------------------------------ */
/*  AG Grid API Shape (minimal — avoid hard dependency)                */
/* ------------------------------------------------------------------ */

export interface AGGridApi {
  setGridOption(key: string, value: unknown): void;
  getFilterModel(): Record<string, unknown>;
  setFilterModel(model: Record<string, unknown> | null): void;
  getColumnDefs(): Array<{ field?: string; headerName?: string; colId?: string; type?: string | string[]; sortable?: boolean; filter?: boolean | string }> | undefined;
  getSelectedRows(): Record<string, unknown>[];
  forEachNode(callback: (node: { data: Record<string, unknown>; setSelected: (selected: boolean) => void; id?: string }) => void): void;
  deselectAll(): void;
  refreshServerSide?(params?: { purge?: boolean }): void;
  refreshCells?(params?: { force?: boolean }): void;
  addEventListener(event: string, listener: (...args: unknown[]) => void): void;
  removeEventListener(event: string, listener: (...args: unknown[]) => void): void;
}

/* ------------------------------------------------------------------ */
/*  AG Grid Filter ↔ GridFilterEntry translation                       */
/* ------------------------------------------------------------------ */

function agFilterToEntries(model: Record<string, unknown>): GridFilterEntry[] {
  const entries: GridFilterEntry[] = [];
  for (const [field, config] of Object.entries(model)) {
    if (!config || typeof config !== 'object') continue;
    const c = config as Record<string, unknown>;
    const filterType = c.filterType as string;

    if (filterType === 'set') {
      entries.push({ field, operator: 'in', value: c.values });
    } else if (filterType === 'number') {
      if (c.type === 'inRange') {
        entries.push({ field, operator: 'range', value: { min: c.filter, max: c.filterTo } });
      } else {
        const op = mapAgNumberOp(c.type as string);
        entries.push({ field, operator: op, value: c.filter });
      }
    } else if (filterType === 'text') {
      if (c.type === 'contains') {
        entries.push({ field, operator: 'contains', value: c.filter });
      } else {
        entries.push({ field, operator: 'eq', value: c.filter });
      }
    } else if (filterType === 'date') {
      if (c.type === 'inRange') {
        entries.push({ field, operator: 'range', value: { min: c.dateFrom, max: c.dateTo } });
      } else {
        entries.push({ field, operator: 'eq', value: c.dateFrom });
      }
    }
  }
  return entries;
}

function mapAgNumberOp(agType: string): FilterOperator {
  switch (agType) {
    case 'equals': return 'eq';
    case 'notEqual': return 'neq';
    case 'greaterThan': return 'gt';
    case 'greaterThanOrEqual': return 'gte';
    case 'lessThan': return 'lt';
    case 'lessThanOrEqual': return 'lte';
    default: return 'eq';
  }
}

function entriesToAgFilter(entries: GridFilterEntry[]): Record<string, unknown> {
  const model: Record<string, unknown> = {};
  for (const e of entries) {
    switch (e.operator) {
      case 'in':
        model[e.field] = { filterType: 'set', values: Array.isArray(e.value) ? e.value : [e.value] };
        break;
      case 'range': {
        const range = e.value as { min: unknown; max: unknown };
        model[e.field] = { filterType: 'number', type: 'inRange', filter: range.min, filterTo: range.max };
        break;
      }
      case 'contains':
        model[e.field] = { filterType: 'text', type: 'contains', filter: e.value };
        break;
      case 'gt':
        model[e.field] = { filterType: 'number', type: 'greaterThan', filter: e.value };
        break;
      case 'lt':
        model[e.field] = { filterType: 'number', type: 'lessThan', filter: e.value };
        break;
      default:
        model[e.field] = { filterType: 'text', type: 'equals', filter: e.value };
    }
  }
  return model;
}

/* ------------------------------------------------------------------ */
/*  AGGridAdapter                                                      */
/* ------------------------------------------------------------------ */

export class AGGridAdapter implements GridAdapter {
  readonly id: string;
  private api: AGGridApi;
  private filterListeners: Array<(filters: GridFilterEntry[]) => void> = [];
  private sortListeners: Array<(sorts: GridSortEntry[]) => void> = [];
  private selectionListeners: Array<(event: GridSelectionEvent) => void> = [];
  private highlightedRowIds: Set<string> = new Set();
  private disposed = false;

  private boundFilterChanged: () => void;
  private boundSortChanged: () => void;
  private boundSelectionChanged: () => void;

  constructor(id: string, api: AGGridApi) {
    this.id = id;
    this.api = api;

    this.boundFilterChanged = this.handleFilterChanged.bind(this);
    this.boundSortChanged = this.handleSortChanged.bind(this);
    this.boundSelectionChanged = this.handleSelectionChanged.bind(this);

    api.addEventListener('filterChanged', this.boundFilterChanged);
    api.addEventListener('sortChanged', this.boundSortChanged);
    api.addEventListener('selectionChanged', this.boundSelectionChanged);
  }

  setData(rows: Record<string, unknown>[]): void {
    this.api.setGridOption('rowData', rows);
  }

  getSelectedRows(): Record<string, unknown>[] {
    return this.api.getSelectedRows();
  }

  getColumnDefs(): GridColumnDef[] {
    const defs = this.api.getColumnDefs() ?? [];
    return defs
      .filter((d) => d.field)
      .map((d) => ({
        field: d.field!,
        headerName: d.headerName ?? d.field!,
        type: inferColumnType(d.type),
        sortable: d.sortable !== false,
        filterable: d.filter !== false,
        colId: d.colId,
      }));
  }

  applyExternalFilter(filters: GridFilterEntry[]): void {
    const model = entriesToAgFilter(filters);
    this.api.setFilterModel(model);
    this.api.refreshServerSide?.({ purge: true });
  }

  getFilterModel(): GridFilterEntry[] {
    return agFilterToEntries(this.api.getFilterModel());
  }

  getSortModel(): GridSortEntry[] {
    // AG Grid v34+ stores sort in column state via getColumnDefs
    const defs = this.api.getColumnDefs() ?? [];
    const entries: GridSortEntry[] = [];
    for (const def of defs) {
      const d = def as Record<string, unknown>;
      if (d.sort && d.field) {
        entries.push({
          field: d.field as string,
          direction: d.sort === 'desc' ? 'desc' : 'asc',
          sortIndex: typeof d.sortIndex === 'number' ? d.sortIndex : entries.length,
        });
      }
    }
    entries.sort((a, b) => (a.sortIndex ?? 0) - (b.sortIndex ?? 0));
    return entries;
  }

  onFilterChange(callback: (filters: GridFilterEntry[]) => void): () => void {
    this.filterListeners.push(callback);
    return () => {
      this.filterListeners = this.filterListeners.filter((l) => l !== callback);
    };
  }

  onSortChange(callback: (sorts: GridSortEntry[]) => void): () => void {
    this.sortListeners.push(callback);
    return () => {
      this.sortListeners = this.sortListeners.filter((l) => l !== callback);
    };
  }

  onSelectionChange(callback: (event: GridSelectionEvent) => void): () => void {
    this.selectionListeners.push(callback);
    return () => {
      this.selectionListeners = this.selectionListeners.filter((l) => l !== callback);
    };
  }

  highlightRows(rowIds: string[]): void {
    this.highlightedRowIds = new Set(rowIds);
    this.api.deselectAll();
    this.api.forEachNode((node) => {
      if (node.id && this.highlightedRowIds.has(node.id)) {
        node.setSelected(true);
      }
    });
  }

  clearHighlights(): void {
    this.highlightedRowIds.clear();
    this.api.deselectAll();
  }

  refresh(): void {
    this.api.refreshCells?.({ force: true });
  }

  destroy(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.api.removeEventListener('filterChanged', this.boundFilterChanged);
    this.api.removeEventListener('sortChanged', this.boundSortChanged);
    this.api.removeEventListener('selectionChanged', this.boundSelectionChanged);
    this.filterListeners = [];
    this.sortListeners = [];
    this.selectionListeners = [];
  }

  /* ---- private event handlers ---- */

  private handleFilterChanged(): void {
    const filters = this.getFilterModel();
    for (const l of this.filterListeners) l(filters);
  }

  private handleSortChanged(): void {
    const sorts = this.getSortModel();
    for (const l of this.sortListeners) l(sorts);
  }

  private handleSelectionChanged(): void {
    const rows = this.getSelectedRows();
    const event: GridSelectionEvent = {
      selectedRows: rows,
      selectedRowIds: rows.map((r) => String(r.id ?? '')),
    };
    for (const l of this.selectionListeners) l(event);
  }
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function inferColumnType(agType?: string | string[]): GridColumnDef['type'] {
  if (!agType) return 'string';
  const t = Array.isArray(agType) ? agType[0] : agType;
  if (t === 'numericColumn' || t === 'numberColumn') return 'number';
  if (t === 'dateColumn') return 'date';
  if (t === 'booleanColumn') return 'boolean';
  return 'string';
}
