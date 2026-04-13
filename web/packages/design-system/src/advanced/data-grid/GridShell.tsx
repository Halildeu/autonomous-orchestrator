/**
 * GridShell — Core AG Grid v34 wrapper.
 *
 * Responsibilities:
 * - AgGridReact rendering with ref forwarding
 * - Theme class injection (ag-theme-quartz, etc.)
 * - Density attribute for CSS variable switching
 * - License guard via setup.ts side-effect import
 * - onGridReady event forwarding
 */
import React, { forwardRef, useCallback, useImperativeHandle, useMemo, useRef } from "react";
import { resolveAccessState, accessStyles, type AccessControlledProps } from '../../internal/access-controller';
import { AgGridReact } from "ag-grid-react";
import type {
  ColDef,
  FilterChangedEvent,
  GridApi,
  GridOptions,
  GridReadyEvent,
  ExcelStyle,
  SideBarDef,
} from "ag-grid-community";

// Side-effect: ensures modules are registered
import "./setup";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------
 */

export type GridTheme = "quartz" | "balham" | "alpine" | "material";
export type GridDensity = "comfortable" | "compact";

export interface GridShellApi<RowData = unknown> {
  getGridApi: () => GridApi<RowData> | null;
}

/** Props for the GridShell component. */
export interface GridShellProps<RowData = unknown> extends AccessControlledProps {
  /** AG Grid column definitions */
  columnDefs: ColDef<RowData>[];
  /** Default column definition applied to all columns */
  defaultColDef?: ColDef<RowData>;
  /** AG Grid options (passed through to AgGridReact) */
  gridOptions?: GridOptions<RowData>;
  /** Row data for client-side mode (undefined for server-side) */
  rowData?: RowData[];
  /** Row model type */
  rowModelType?: "clientSide" | "serverSide" | "infinite";
  /** AG Grid sidebar definition */
  sideBar?: SideBarDef | string | string[] | boolean;
  /** AG Grid locale text overrides */
  localeText?: Record<string, string>;
  /** Excel export styles */
  excelStyles?: ExcelStyle[];
  /** Loading overlay template */
  overlayLoadingTemplate?: string;
  /** No-rows overlay template */
  overlayNoRowsTemplate?: string;
  /** Row height (overrides density default) */
  rowHeight?: number;
  /** Row selection config */
  rowSelection?: GridOptions<RowData>["rowSelection"];
  /** Theme name */
  theme?: GridTheme;
  /** Density setting */
  density?: GridDensity;
  /** Animate rows */
  animateRows?: boolean;
  /** Grid ready callback */
  onGridReady?: (event: GridReadyEvent<RowData>) => void;
  /** Row double-click callback */
  onRowDoubleClick?: (row: RowData) => void;
  /** Pagination changed callback (for useAgGridTablePagination) */
  onPaginationChanged?: (event: { api: GridApi<RowData> }) => void;
  /** Container height */
  height?: number | string;
  /** Container className */
  className?: string;
  /** Unique key for grid remounting */
  gridKey?: string;
  /** Enable AG Grid integrated charts (requires IntegratedChartsModule) */
  enableCharts?: boolean;
  /** AG Charts theme overrides for integrated charts */
  chartThemeOverrides?: Record<string, unknown>;
  /** Callback fired when any filter (column or advanced) changes */
  onFilterChanged?: (event: FilterChangedEvent<RowData>) => void;
  /** Children rendered below the grid (e.g., pagination) */
  children?: React.ReactNode;
}

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const DENSITY_ROW_HEIGHT: Record<GridDensity, number> = {
  comfortable: 48,
  compact: 36,
};

const DEFAULT_COL_DEF: ColDef = {
  sortable: true,
  filter: "agMultiColumnFilter",
  floatingFilter: true,
  resizable: true,
  enableRowGroup: true,
  enablePivot: true,
  enableValue: true,
  minWidth: 120,
  flex: 1,
  menuTabs: ["generalMenuTab", "filterMenuTab", "columnsMenuTab"],
};

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

function GridShellInner<RowData = unknown>(
  props: GridShellProps<RowData>,
  ref: React.Ref<GridShellApi<RowData>>,
): React.ReactElement {
  const {
    columnDefs,
    defaultColDef,
    gridOptions,
    rowData,
    rowModelType = "clientSide",
    sideBar,
    localeText,
    excelStyles,
    overlayLoadingTemplate,
    overlayNoRowsTemplate,
    rowHeight,
    rowSelection,
    theme = "quartz",
    density = "comfortable",
    animateRows = true,
    onGridReady,
    onRowDoubleClick,
    onPaginationChanged,
    height = 600,
    enableCharts = false,
    chartThemeOverrides,
    onFilterChanged,
    className,
    gridKey,
    children,
    access,
    accessReason,
  } = props;

  const accessState = resolveAccessState(access);
  if (accessState.isHidden) return null as unknown as React.ReactElement;

  const gridApiRef = useRef<GridApi<RowData> | null>(null);

  useImperativeHandle(ref, () => ({
    getGridApi: () => gridApiRef.current,
  }));

  const resolvedRowHeight = rowHeight ?? DENSITY_ROW_HEIGHT[density];
  const themeClassName = `ag-theme-${theme}`;

  const mergedDefaultColDef = useMemo(
    () => ({ ...DEFAULT_COL_DEF, ...defaultColDef }),
    [defaultColDef],
  );

  const handleGridReady = useCallback(
    (event: GridReadyEvent<RowData>) => {
      gridApiRef.current = event.api;
      onGridReady?.(event);
    },
    [onGridReady],
  );

  const handleRowDoubleClicked = useCallback(
    (event: { data: RowData | undefined }) => {
      if (event.data && onRowDoubleClick) {
        onRowDoubleClick(event.data);
      }
    },
    [onRowDoubleClick],
  );

  const handlePaginationChanged = useCallback(
    () => {
      if (onPaginationChanged && gridApiRef.current) {
        onPaginationChanged({ api: gridApiRef.current });
      }
    },
    [onPaginationChanged],
  );

  const handleFilterChanged = useCallback(
    (event: FilterChangedEvent<RowData>) => {
      onFilterChanged?.(event);
      // For SSRM, trigger server refresh so the datasource re-fetches with updated filterModel
      if (rowModelType === "serverSide" && gridApiRef.current) {
        gridApiRef.current.refreshServerSide?.({ purge: true });
      }
    },
    [onFilterChanged, rowModelType],
  );

  return (
    <div
      data-access-state={accessState.state}
      className={[className ?? "", accessStyles(accessState.state)].join(" ").trim() || undefined}
      data-component="grid-shell"
      data-density={density}
      title={accessReason}
    >
      <div
        className={themeClassName}
        style={{ width: "100%", height: typeof height === "number" ? `${height}px` : height }}
      >
        <AgGridReact<RowData>
          key={gridKey}
          rowData={rowModelType === "clientSide" ? rowData : undefined}
          columnDefs={columnDefs}
          // eslint-disable-next-line @typescript-eslint/no-explicit-any -- AG Grid ColDef typing gap
          defaultColDef={mergedDefaultColDef as any}
          rowModelType={rowModelType}
          sideBar={sideBar}
          localeText={localeText}
          excelStyles={excelStyles}
          overlayLoadingTemplate={overlayLoadingTemplate}
          overlayNoRowsTemplate={overlayNoRowsTemplate}
          rowHeight={resolvedRowHeight}
          headerHeight={density === "compact" ? 40 : 48}
          rowSelection={rowSelection ?? { mode: 'multiRow' as const, checkboxes: true, headerCheckbox: true }}
          animateRows={animateRows}
          rowGroupPanelShow="always"
          enableRangeSelection
          groupDefaultExpanded={0}
          autoGroupColumnDef={{
            floatingFilter: true,
            filter: 'agTextColumnFilter',
            minWidth: 200,
          }}
          // groupTotalRow="bottom" — disabled: duplicates group header values
          pagination
          paginationPageSize={50}
          paginationPageSizeSelector={false}
          suppressPaginationPanel
          // enableAdvancedFilter — AG Grid limitation: disables floating filters + context menu
          // Custom filter builder will be implemented in design-system instead
          enableCharts={enableCharts}
          chartThemeOverrides={chartThemeOverrides}
          statusBar={{
            statusPanels: [
              { statusPanel: 'agTotalAndFilteredRowCountComponent', align: 'left' },
              { statusPanel: 'agSelectedRowCountComponent', align: 'left' },
              { statusPanel: 'agAggregationComponent', align: 'right' },
            ],
          }}
          getContextMenuItems={(params) => {
            const setAggFunc = (p: typeof params, fn: string | null) => {
              if (p.column && p.api) {
                const colId = p.column.getColId();
                p.api.applyColumnState({
                  state: [{ colId, aggFunc: fn }],
                });
              }
            };
            const defaults = params.defaultItems ?? [];
            return [
              ...defaults,
              'separator',
              {
                name: 'Bu değere göre filtrele',
                icon: '<span style="font-size:12px">🔍</span>',
                disabled: !params.value,
                action: () => {
                  if (params.column && params.api) {
                    const colId = params.column.getColId();
                    params.api.setColumnFilterModel(colId, {
                      filterType: 'text',
                      type: 'equals',
                      filter: String(params.value),
                    }).then(() => params.api.onFilterChanged());
                  }
                },
              },
              {
                name: 'Satırı üste sabitle',
                icon: '<span style="font-size:12px">📌</span>',
                disabled: !params.node?.data,
                action: () => {
                  if (params.api && params.node?.data) {
                    const existing = params.api.getGridOption('pinnedTopRowData') ?? [];
                    params.api.setGridOption('pinnedTopRowData', [...existing, params.node.data]);
                  }
                },
              },
              {
                name: 'Sabitlemeleri kaldır',
                icon: '<span style="font-size:12px">📌</span>',
                action: () => {
                  params.api?.setGridOption('pinnedTopRowData', []);
                  params.api?.setGridOption('pinnedBottomRowData', []);
                },
              },
              'separator',
              {
                name: 'Sütun Hesaplama',
                icon: '<span style="font-size:12px">∑</span>',
                disabled: !params.column,
                subMenu: [
                  { name: 'Toplam (Sum)', action: () => setAggFunc(params, 'sum') },
                  { name: 'Ortalama (Avg)', action: () => setAggFunc(params, 'avg') },
                  { name: 'Sayı (Count)', action: () => setAggFunc(params, 'count') },
                  { name: 'Min', action: () => setAggFunc(params, 'min') },
                  { name: 'Max', action: () => setAggFunc(params, 'max') },
                  { name: 'İlk (First)', action: () => setAggFunc(params, 'first') },
                  { name: 'Son (Last)', action: () => setAggFunc(params, 'last') },
                  'separator',
                  { name: 'Hesaplamayı kaldır', action: () => setAggFunc(params, null) },
                ],
              },
            ];
          }}
          popupParent={typeof document !== "undefined" ? document.body : undefined}
          onGridReady={handleGridReady}
          onRowDoubleClicked={handleRowDoubleClicked}
          onPaginationChanged={handlePaginationChanged}
          onFilterChanged={handleFilterChanged}
          {...gridOptions}
        />
      </div>
      {children}
    </div>
  );
}

/** Core AG Grid shell with theme, density, selection, empty state, and imperative API access. 
 * @example
 * ```tsx
 * <GridShell />
 * ```
 * @since 1.0.0
 * @see [Docs](https://design.mfe.dev/components/grid-shell)
 */
export const GridShell = forwardRef(GridShellInner) as <RowData = unknown>(
  props: GridShellProps<RowData> & { ref?: React.Ref<GridShellApi<RowData>> },
) => React.ReactElement;

// @ts-expect-error -- generic forwardRef cast loses static properties
GridShell.displayName = "GridShell";

export default GridShell;
