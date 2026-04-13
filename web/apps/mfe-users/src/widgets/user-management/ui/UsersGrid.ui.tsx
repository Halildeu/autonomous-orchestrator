import React, { useCallback, useMemo, useState, useEffect, useRef } from 'react';
import type {
  ColDef,
  GridReadyEvent,
  IServerSideGetRowsParams,
  GridOptions,
  GridApi,
  ProcessCellForExportParams,
  AdvancedFilterModel as AgAdvancedFilterModel,
} from 'ag-grid-community';
// MF virtual modules in dev don't re-export named bindings (MF #376),
// so import grid utilities from @mfe/design-system directly.
import type { GridExportConfig } from 'mfe_reporting/grid';
import { buildEntityGridQueryParams } from '@mfe/design-system';
import { buildColDefs, buildProcessCellCallback, type ColumnMeta } from '@mfe/design-system/advanced/data-grid';
// Ağır AG Grid bağımlılıklarını ilk ekranda yüklememek için lazy-load
const EntityGridTemplate = React.lazy(() =>
  import('@mfe/design-system').then((m) => ({ default: m.EntityGridTemplate })),
);
import type { UserSummary, UserModuleAccessLevel } from '@mfe/shared-types';
import { Badge, Button, Empty, useDownloadWithProgress, type BadgeTone } from '@mfe/design-system';
import UserActions from './UserActions.ui';
import { fetchUsers } from '../../../entities/user/api/users.api';
import type { UsersQueryParams } from '../../../features/user-management/model/user-management.types';
import { useUsersI18n } from '../../../i18n/useUsersI18n';

declare global {
  interface Window {
    usersGridApi?: GridApi<UserSummary>;
  }
}

type ToastType = 'success' | 'error' | 'warning';

const showToast = (type: ToastType, text: string) => {
  try {
    window.dispatchEvent(new CustomEvent('app:toast', { detail: { type, text } }));
  } catch {
    if (process.env.NODE_ENV !== 'production') {
      const fallback = type === 'error' ? 'error' : 'log';
      console[fallback](text);
    }
  }
};

const MODULE_LEVEL_LABELS: Record<UserModuleAccessLevel, string> = {
  NONE: 'users.filters.moduleLevel.none',
  VIEW: 'users.filters.moduleLevel.view',
  EDIT: 'users.filters.moduleLevel.edit',
  MANAGE: 'users.filters.moduleLevel.manage',
};

const MODULE_LEVEL_COLORS: Record<UserModuleAccessLevel, BadgeTone> = {
  NONE: 'muted',
  VIEW: 'info',
  EDIT: 'warning',
  MANAGE: 'danger',
};

const SERVER_CACHE_BLOCK_SIZE = 50;

const GRID_VARIANT_ID = 'mfe-users/users-grid';
const GRID_VARIANT_SCHEMA_VERSION = 1;

type GridApiWithOptions = GridApi<UserSummary> & {
  getGridOption?: (key: string) => unknown;
  setGridOption?: (key: string, value: unknown) => void;
  refreshServerSide?: (params?: { purge?: boolean }) => void;
};

type AdvancedJoinNode = {
  filterType: 'join';
  type?: 'AND' | 'OR';
  conditions?: AgAdvancedFilterModel[];
};

type AdvancedConditionNode = {
  colId?: string;
  type?: string;
  filter?: unknown;
  filterTo?: unknown;
};

type _ServerSideRequestExtras = IServerSideGetRowsParams<UserSummary>['request'] & {
  sortModel?: Array<{ colId?: string; sort?: 'asc' | 'desc' }>;
};

type ServerSideParamsWithCallbacks = IServerSideGetRowsParams<UserSummary> & {
  success?: (payload: { rowData: UserSummary[]; rowCount: number }) => void;
  successCallback?: (rowData: UserSummary[], rowCount: number) => void;
  fail?: () => void;
  failCallback?: () => void;
};

const isJoinNode = (node: AgAdvancedFilterModel | null | undefined): node is AdvancedJoinNode => {
  if (!node || typeof node !== 'object') {
    return false;
  }
  return (node as { filterType?: string }).filterType === 'join';
};

interface UsersGridProps {
  onSelectUser: (user: UserSummary) => void;
  isFullscreen?: boolean;
  onGridReady?: (event: GridReadyEvent<UserSummary>) => void;
  onLoadingChange?: (loading: boolean) => void;
}

type GridAccessState = 'idle' | 'unauthorized' | 'profile-missing' | 'network-error';

const INLINE_ONLY_ACCESS_STATES = new Set<GridAccessState>(['unauthorized', 'profile-missing']);

const UsersGrid: React.FC<UsersGridProps> = ({
  onSelectUser,
  isFullscreen = false,
  onGridReady: onGridReadyProp,
  onLoadingChange,
}) => {
  const { t, locale } = useUsersI18n();
  const { downloadWithProgress } = useDownloadWithProgress();
  const gridApiRef = useRef<GridApi<UserSummary> | null>(null);
  const [dataSourceMode, setDataSourceMode] = useState<'server' | 'client'>('server');
  const [clientRows, setClientRows] = useState<UserSummary[]>([]);
  const [gridAccessState, setGridAccessState] = useState<GridAccessState>('idle');
  const [accessProbeReady, setAccessProbeReady] = useState(false);
  const [retryKey, setRetryKey] = useState(0);
  const notifiedStatesRef = React.useRef<Set<GridAccessState>>(new Set());
  const gridAccessStateRef = React.useRef<GridAccessState>('idle');
  const debugLog = useCallback(
    (...args: unknown[]) => {
      if (process.env.NODE_ENV !== 'production') {
        console.debug('[UsersGrid]', ...args);
      }
    },
    [],
  );

  const notifyOnce = useCallback((state: GridAccessState, type: ToastType, message: string) => {
    if (state === 'idle') {
      return;
    }
    if (INLINE_ONLY_ACCESS_STATES.has(state)) {
      return;
    }
    if (notifiedStatesRef.current.has(state)) {
      return;
    }
    notifiedStatesRef.current.add(state);
    showToast(type, message);
  }, []);

  const setGridState = useCallback((nextState: GridAccessState) => {
    gridAccessStateRef.current = nextState;
    setGridAccessState(nextState);
    if (nextState === 'idle') {
      notifiedStatesRef.current.clear();
    }
  }, []);
  const formatModulePermissions = useCallback(
    (permissions?: UserSummary['modulePermissions']) => {
      if (!permissions?.length) {
        return '';
      }
      return permissions
        .map((permission) => {
          const levelKey = MODULE_LEVEL_LABELS[permission.level];
          const levelLabel = levelKey ? t(levelKey) : permission.level;
          return `${permission.moduleLabel ?? permission.moduleKey} (${levelLabel})`;
        })
        .join(', ');
    },
    [t, locale],
  );

  /* ------------------------------------------------------------------ */
  /*  Column metadata — declarative column definitions via column-system  */
  /* ------------------------------------------------------------------ */

  const localeCode = locale === 'tr' ? 'tr-TR' : locale === 'en' ? 'en-US' : locale === 'de' ? 'de-DE' : locale === 'es' ? 'es-ES' : 'tr-TR';

  const columnMeta = useMemo<ColumnMeta[]>(() => [
    { field: 'fullName', headerNameKey: 'users.grid.columns.fullName', columnType: 'bold-text', minWidth: 180 },
    { field: 'email', headerNameKey: 'users.grid.columns.email', columnType: 'text', minWidth: 220 },
    {
      field: 'role', headerNameKey: 'users.grid.columns.role', columnType: 'badge', width: 140,
      variantMap: { ADMIN: 'danger', USER: 'info' },
      defaultVariant: 'info',
      labelMap: { ADMIN: 'users.filters.role.admin', USER: 'users.filters.role.user' },
      filterValues: ['ADMIN', 'USER'],
    },
    {
      field: 'status', headerNameKey: 'users.grid.columns.status', columnType: 'status', width: 140,
      statusMap: {
        ACTIVE: { variant: 'success', labelKey: 'users.filters.status.active' },
        INACTIVE: { variant: 'muted', labelKey: 'users.filters.status.inactive' },
        INVITED: { variant: 'warning', labelKey: 'users.filters.status.invited' },
        SUSPENDED: { variant: 'danger', labelKey: 'users.filters.status.suspended' },
      },
    },
    { field: 'sessionTimeoutMinutes', headerNameKey: 'users.grid.columns.sessionTimeoutMinutes', columnType: 'number', width: 160, suffix: 'dk' },
    { field: 'lastLoginAt', headerNameKey: 'users.grid.columns.lastLoginAt', columnType: 'date', width: 180, format: 'datetime' },
  ], []);

  /* Custom columns that column-system can't express */
  const customColumnDefs = useMemo<ColDef<UserSummary>[]>(() => [
    {
      headerName: t('users.grid.columns.roles'),
      field: 'role',
      minWidth: 180,
      filter: 'agTextColumnFilter',
      cellRenderer: ({ data }) => {
        const roleName = data?.role;
        if (!roleName) {
          return <span className="text-sm text-text-subtle">—</span>;
        }
        return (
          <div className="flex flex-wrap gap-1">
            <Badge variant="info">{roleName}</Badge>
          </div>
        );
      },
    },
    {
      headerName: t('users.grid.columns.actions'),
      field: 'id',
      width: 120,
      sortable: false,
      filter: false,
      floatingFilter: false,
      cellRenderer: ({ data }) =>
        data ? <UserActions user={data} onSelect={() => onSelectUser(data)} /> : null,
      pinned: 'right',
    },
  ], [onSelectUser, t]);

  /* Merge column-system output with custom columns */
  const columnDefs = useMemo<ColDef<UserSummary>[]>(() => {
    const metaDefs = buildColDefs<UserSummary>(columnMeta, t, localeCode) as ColDef<UserSummary>[];
    // Insert modulePermissions before actions (between lastLoginAt and actions)
    return [...metaDefs, ...customColumnDefs];
  }, [columnMeta, customColumnDefs, t, localeCode]);

  const gridOptions = useMemo<GridOptions<UserSummary>>(
    () => ({
      cellSelection: true,
      multiSortKey: 'ctrl',
      rowGroupPanelShow: 'always',
      // AG Grid v34: cacheBlockSize sadece serverSide row modelde geçerli
      ...(dataSourceMode === 'server'
        ? {
            cacheBlockSize: SERVER_CACHE_BLOCK_SIZE,
            maxBlocksInCache: 1,
            blockLoadDebounceMillis: 25,
          }
        : {}),
    }),
    [dataSourceMode],
  );

  const exportConfig = useMemo<GridExportConfig<UserSummary>>(
    () => ({
      fileBaseName: 'kullanicilar',
      sheetName: 'Kullanıcılar',
      processCellCallback: (params: ProcessCellForExportParams<UserSummary>) => {
        if (params.column?.getColId() === 'modulePermissions') {
          return formatModulePermissions(params.node?.data?.modulePermissions);
        }
        return params.value;
      },
      csvColumnSeparator: ';',
      csvBom: true,
    }),
    [formatModulePermissions],
  );

  const localeText = useMemo(() => {
    // Tüm diller için gelişmiş filtre ve yan panel metinlerini i18n üzerinden veriyoruz
    const groupText = t('users.grid.locale.groupPanel');
    const valueText = t('users.grid.locale.valuePanel');
    return {
      // Grup paneli
      rowGroupPanel: groupText,
      dropZoneColumnGroup: groupText,
      rowGroupColumnsEmptyMessage: groupText,
      dragHereToSetColumnRowGroup: groupText,
      dragHereToSetRowGroup: groupText,
      dropZoneColumnValue: valueText,
      // Yan panel başlıkları
      filters: t('users.grid.locale.filters'),
      columns: t('users.grid.locale.columns'),
      // Gelişmiş filtre
      advancedFilter: t('users.grid.locale.advancedFilter'),
      advancedFilterBuilder: t('users.grid.locale.advancedFilterBuilder'),
      advancedFilterButtonTooltip: t('users.grid.locale.advancedFilterButtonTooltip'),
      advancedFilterBuilderAdd: t('users.grid.locale.advancedFilterBuilderAdd'),
      advancedFilterBuilderRemove: t('users.grid.locale.advancedFilterBuilderRemove'),
      advancedFilterJoinOperator: t('users.grid.locale.advancedFilterJoinOperator'),
      advancedFilterAnd: t('users.grid.locale.advancedFilterAnd'),
      advancedFilterOr: t('users.grid.locale.advancedFilterOr'),
      advancedFilterValidationMissingColumn: t('users.grid.locale.advancedFilterValidationMissingColumn'),
      advancedFilterValidationMissingOption: t('users.grid.locale.advancedFilterValidationMissingOption'),
      advancedFilterValidationMissingValue: t('users.grid.locale.advancedFilterValidationMissingValue'),
      advancedFilterApply: t('users.grid.locale.advancedFilterApply'),
    } as Record<string, string>;
  }, [t]);

  const mapAdvancedFilterModel = useCallback(
    (model: AgAdvancedFilterModel | null | undefined) => {
      if (!model) return null;

      const fieldMap: Record<string, string> = {
        fullName: 'name',
        email: 'email',
        role: 'role',
        lastLoginAt: 'lastLogin',
        sessionTimeoutMinutes: 'sessionTimeoutMinutes',
      };

      type BackendOp =
        | 'equals'
        | 'notEqual'
        | 'contains'
        | 'notContains'
        | 'lessThan'
        | 'greaterThan'
        | 'inRange';

      const mapOp = (type: string | undefined): BackendOp | null => {
        switch (type) {
          case 'equals':
          case 'notEqual':
          case 'contains':
          case 'notContains':
          case 'lessThan':
          case 'greaterThan':
          case 'inRange':
            return type;
          case 'lessThanOrEqual':
            return 'lessThan';
          case 'greaterThanOrEqual':
            return 'greaterThan';
          default:
            return null;
        }
      };

      const conditions: { field: string; op: BackendOp; value?: unknown; value2?: unknown }[] = [];

      const visit = (node: AgAdvancedFilterModel | null | undefined) => {
        if (!node) return;
        if (isJoinNode(node)) {
          (node.conditions ?? []).forEach((child) => visit(child));
          return;
        }
        const conditionNode = node as AdvancedConditionNode;
        const colId = conditionNode.colId;
        if (!colId) return;
        const backendField = fieldMap[colId];
        if (!backendField) return;
        const op = mapOp(conditionNode.type);
        if (!op) return;
        const value = conditionNode.filter;
        const value2 = conditionNode.filterTo;
        const condition: { field: string; op: BackendOp; value?: unknown; value2?: unknown } = {
          field: backendField,
          op,
        };
        if (value !== undefined) {
          condition.value = value;
        }
        if (op === 'inRange' && value2 !== undefined) {
          condition.value2 = value2;
        }
        conditions.push(condition);
      };

      visit(model);

      if (conditions.length === 0) {
        return null;
      }

      const logic = isJoinNode(model) && model.type === 'OR' ? 'or' : 'and';

      return {
        logic,
        conditions,
      };
    },
    [],
  );

  const createServerSideDatasource = useCallback(
    ({ gridApi }: { gridApi: GridApi<UserSummary> }) => {
      // Aynı aralık/sort/filter için eşzamanlı çağrıları tek backend isteğine indirger
      const inFlight = new Map<string, IServerSideGetRowsParams<UserSummary>[]>();
      const buildKey = (req: IServerSideGetRowsParams<UserSummary>['request']) =>
        JSON.stringify({ s: req.startRow, e: req.endRow, f: req.filterModel ?? {}, o: req.sortModel ?? [] });

      const ssrmSuccessFor = (p: IServerSideGetRowsParams<UserSummary>, items: UserSummary[], total: number) => {
        const paramsWithCallbacks = p as ServerSideParamsWithCallbacks;
        if (typeof paramsWithCallbacks.success === 'function') {
          paramsWithCallbacks.success({ rowData: items, rowCount: total });
          return;
        }
        if (typeof paramsWithCallbacks.successCallback === 'function') {
          paramsWithCallbacks.successCallback(items, total);
          return;
        }
        if (process.env.NODE_ENV !== 'production') {
          console.warn('[UsersGrid] SSRM success handler not found');
        }
      };
      const ssrmFailFor = (p: IServerSideGetRowsParams<UserSummary>) => {
        const paramsWithCallbacks = p as ServerSideParamsWithCallbacks;
        if (typeof paramsWithCallbacks.fail === 'function') {
          paramsWithCallbacks.fail();
          return;
        }
        if (typeof paramsWithCallbacks.failCallback === 'function') {
          paramsWithCallbacks.failCallback();
          return;
        }
        if (process.env.NODE_ENV !== 'production') {
          console.warn('[UsersGrid] SSRM fail handler not found');
        }
      };

      return {
        getRows: async (params: IServerSideGetRowsParams<UserSummary>) => {
          if (gridAccessStateRef.current !== 'idle') {
            ssrmSuccessFor(params, [], 0);
            return;
          }

          const requestedBlockSize = params.request.endRow - params.request.startRow;
          const effectiveBlockSize = Number.isFinite(requestedBlockSize) && requestedBlockSize > 0
            ? requestedBlockSize
            : SERVER_CACHE_BLOCK_SIZE;
          const startRow = params.request.startRow ?? 0;
          const pageNumber = Math.floor(startRow / effectiveBlockSize) + 1;
          const requestLabel = `${pageNumber}:${effectiveBlockSize}:${startRow}-${params.request.endRow ?? startRow + effectiveBlockSize}`;

          const key = buildKey(params.request);
          if (inFlight.has(key)) {
            inFlight.get(key)!.push(params);
            if (process.env.NODE_ENV !== 'production') {
              console.debug('[UsersGrid] server:getRows:coalesced', requestLabel);
            }
            return;
          }
          inFlight.set(key, [params]);

          // Quick filter metnini grid options'tan çek (SSRM global arama desteği)
          const apiWithOptions = gridApi as GridApiWithOptions;
          const quickFilterText = typeof apiWithOptions.getGridOption === 'function'
            ? apiWithOptions.getGridOption('quickFilterText') ?? ''
            : '';

          debugLog('server:getRows:start', requestLabel, {
            request: params.request,
            effectiveBlockSize,
            pageNumber,
            quickFilterText,
          });
          onLoadingChange?.(true);
          try {
            const baseParams = buildEntityGridQueryParams({
              request: params.request,
              quickFilterText,
              mapAdvancedFilter: mapAdvancedFilterModel,
              multiSearchParams: (gridApi as unknown as Record<string, unknown>).__multiSearchParams as Record<string, string> | undefined,
              mapFilterModel: (model) => {
                const next: Partial<UsersQueryParams> = {};
                const statusFilter = (model as typeof params.request.filterModel).status as { values?: unknown[] } | undefined;
                if (statusFilter?.values && statusFilter.values.length > 0) {
                  next.status = String(statusFilter.values[0]) as UsersQueryParams['status'];
                }
                const roleFilter = (model as typeof params.request.filterModel).role as { values?: unknown[] } | undefined;
                if (roleFilter?.values && roleFilter.values.length > 0) {
                  next.role = String(roleFilter.values[0]) as UsersQueryParams['role'];
                }
                const nameFilter = (model as typeof params.request.filterModel).fullName as { filter?: unknown } | undefined;
                const emailFilter = (model as typeof params.request.filterModel).email as { filter?: unknown } | undefined;
                const textFilterValue = nameFilter?.filter ?? emailFilter?.filter;
                if (typeof textFilterValue === 'string' && textFilterValue.trim().length > 0) {
                  next.search = textFilterValue.trim();
                }
                return next;
              },
            }) as UsersQueryParams;

            const response = await fetchUsers(baseParams);
            const reason = response.meta?.reason;
            if (reason === 'profile-missing') {
              setGridState('profile-missing');
              debugLog('server:getRows:profile-missing', requestLabel, { queryParams: baseParams });
              notifyOnce('profile-missing', 'warning', 'Profiliniz henüz oluşturulmamış. Lütfen sistem yöneticisiyle iletişime geçin.');
              const batch = inFlight.get(key) ?? [];
              batch.forEach((p) => ssrmSuccessFor(p, [], 0));
              return;
            }
            if (reason === 'unauthorized') {
              setGridState('unauthorized');
              debugLog('server:getRows:unauthorized', requestLabel, { queryParams: baseParams });
              notifyOnce('unauthorized', 'warning', 'Kullanıcı verilerini görmek için yetkiniz bulunmuyor.');
              const batch = inFlight.get(key) ?? [];
              batch.forEach((p) => ssrmSuccessFor(p, [], 0));
              return;
            }
            if (reason === 'network-error') {
              setGridState('network-error');
              debugLog('server:getRows:network-error', requestLabel, { queryParams: baseParams });
              notifyOnce('network-error', 'error', 'Kullanıcı listesi alınamadı. Lütfen bağlantınızı kontrol edin.');
              const batch = inFlight.get(key) ?? [];
              batch.forEach((p) => ssrmSuccessFor(p, [], 0));
              return;
            }
            setGridState('idle');
            const items = response.items ?? [];
            const total = response.total ?? items.length;
            debugLog('server:getRows:success', requestLabel, {
              queryParams: baseParams,
              returnedItems: items.length,
              total,
            });
            const batch = inFlight.get(key) ?? [];
            batch.forEach((p) => ssrmSuccessFor(p, items, total));
          } catch (error: unknown) {
            if (process.env.NODE_ENV !== 'production') {
              console.error('Kullanıcılar yüklenirken hata oluştu', error);
            }
            setGridState('network-error');
            debugLog('server:getRows:error', requestLabel, error);
            notifyOnce('network-error', 'error', error instanceof Error ? error.message : 'Kullanıcılar yüklenirken hata oluştu.');
            const batch = inFlight.get(key) ?? [];
            batch.forEach((p) => ssrmSuccessFor(p, [], 0));
          } finally {
            onLoadingChange?.(false);
            inFlight.delete(key);
            debugLog('server:getRows:complete', requestLabel);
          }
        },
      };
    },
    [debugLog, onLoadingChange],
  );

  const handleGridReady = useCallback(
    (event: GridReadyEvent<UserSummary>) => {
      gridApiRef.current = event.api;
      // Runtime debug: grid API'yi pencereden erişilebilir yap
      try {
        window.usersGridApi = event.api;
        const apiWithOptions = event.api as GridApiWithOptions;
        debugLog('gridReady', {
          serverMode: dataSourceMode === 'server',
          hasSetServerSideDatasource: typeof apiWithOptions.setGridOption === 'function',
          rowModelType: apiWithOptions.getGridOption?.('rowModelType'),
        });
      } catch {
        // no-op: debug için pencere ataması başarısız olabilir
      }
      onGridReadyProp?.(event);
    },
    [onGridReadyProp, debugLog, dataSourceMode],
  );

  const loadClientData = useCallback(async () => {
    onLoadingChange?.(true);
    try {
      // Client modda tüm kullanıcıları çekmek için limitsiz çağrı yapıyoruz (pageSize=0 -> backend unpaged)
      const response = await fetchUsers({ page: 1, pageSize: 0 });
      if (response.meta?.reason === 'unauthorized') {
        setGridState('unauthorized');
        notifyOnce('unauthorized', 'warning', 'Kullanıcı verilerine erişim yetkisi bulunmuyor.');
        setClientRows([]);
        return;
      }
      if (response.meta?.reason === 'profile-missing') {
        setGridState('profile-missing');
        notifyOnce('profile-missing', 'warning', 'Profiliniz henüz oluşturulmamış. Lütfen sistem yöneticisiyle iletişime geçin.');
        setClientRows([]);
        return;
      }
      if (response.meta?.reason === 'network-error') {
        setGridState('network-error');
        notifyOnce('network-error', 'error', 'Kullanıcı verileri sunucudan alınamadı.');
        setClientRows([]);
        return;
      }
      setGridState('idle');
      setClientRows(response.items ?? []);
    } catch (error: unknown) {
      if (process.env.NODE_ENV !== 'production') {
        console.error('Kullanıcılar yüklenirken hata oluştu (client mode)', error);
      }
      setGridState('network-error');
      notifyOnce('network-error', 'error', error instanceof Error ? error.message : 'Kullanıcı verileri yüklenemedi.');
    } finally {
      onLoadingChange?.(false);
    }
  }, [notifyOnce, onLoadingChange, setGridState]);

  const runAccessProbe = useCallback(async () => {
    if (dataSourceMode !== 'server') {
      setAccessProbeReady(true);
      return;
    }

    setAccessProbeReady(false);
    onLoadingChange?.(true);
    try {
      const response = await fetchUsers({ page: 1, pageSize: 1 });
      const reason = response.meta?.reason;

      if (reason === 'unauthorized') {
        setGridState('unauthorized');
        notifyOnce('unauthorized', 'warning', 'Kullanıcı verilerini görmek için yetkiniz bulunmuyor.');
        return;
      }

      if (reason === 'profile-missing') {
        setGridState('profile-missing');
        notifyOnce('profile-missing', 'warning', 'Profiliniz henüz oluşturulmamış. Lütfen sistem yöneticisiyle iletişime geçin.');
        return;
      }

      if (reason === 'network-error') {
        setGridState('network-error');
        notifyOnce('network-error', 'error', 'Kullanıcı listesi alınamadı. Lütfen bağlantınızı kontrol edin.');
        return;
      }

      setGridState('idle');
    } catch (error: unknown) {
      setGridState('network-error');
      notifyOnce('network-error', 'error', error instanceof Error ? error.message : 'Kullanıcı listesi alınamadı. Lütfen bağlantınızı kontrol edin.');
    } finally {
      setAccessProbeReady(true);
      onLoadingChange?.(false);
    }
  }, [dataSourceMode, notifyOnce, onLoadingChange, setGridState]);

  useEffect(() => {
    void runAccessProbe();
  }, [runAccessProbe, retryKey]);

  useEffect(() => {
    if (dataSourceMode === 'client') {
      loadClientData();
    }
  }, [dataSourceMode, loadClientData]);

  const modeSelector = useMemo(
    () => (
      <div className="flex items-center gap-3 text-sm text-text-secondary">
        <span className="font-semibold text-text-primary">{t('users.grid.mode.label')}</span>
        <select
          className="rounded-xl border border-border-subtle bg-surface-default px-3 py-1 text-sm font-medium text-text-secondary shadow-xs focus:outline-hidden focus:ring-2 focus:ring-selection-outline"
          value={dataSourceMode}
          onChange={(event) => setDataSourceMode(event.target.value as 'server' | 'client')}
        >
          <option value="server">{t('users.grid.mode.server')}</option>
          <option value="client">{t('users.grid.mode.client')}</option>
        </select>
        {dataSourceMode === 'client' && (
          <button
            type="button"
            onClick={loadClientData}
            className="rounded-lg bg-action-primary px-3 py-1 text-xs font-semibold text-action-primary-text shadow-xs transition hover:opacity-90"
          >
            Yenile
          </button>
        )}
      </div>
    ),
    [dataSourceMode, loadClientData, t],
  );

  const handleServerExport = useCallback(
    async (format: 'excel' | 'csv', params: { filterModel: Record<string, unknown>; sortModel: unknown[]; quickFilterText: string }) => {
      const qs = new URLSearchParams();
      // Sort
      const sortModel = params.sortModel as Array<{ colId: string; sort: string }>;
      if (sortModel.length > 0) {
        qs.set('sort', sortModel.map((c) => `${c.colId},${c.sort}`).join(';'));
      }
      // Column filters
      for (const [colId, model] of Object.entries(params.filterModel)) {
        const m = model as Record<string, unknown>;
        if (colId === 'status' && m.values) {
          qs.set('status', String((m.values as unknown[])[0]));
        } else if (colId === 'role' && m.values) {
          qs.set('role', String((m.values as unknown[])[0]));
        } else if ((colId === 'fullName' || colId === 'email') && m.filter) {
          qs.set('search', String(m.filter));
        }
      }
      // Quick filter
      if (params.quickFilterText?.trim()) {
        qs.set('search', params.quickFilterText.trim());
      }
      const ext = format === 'excel' ? 'xlsx' : 'csv';
      const url = `/api/users/export.${ext}${qs.toString() ? '?' + qs.toString() : ''}`;
      await downloadWithProgress(url, {
        filename: `kullanicilar.${ext}`,
        title: 'Kullanıcılar dışa aktarılıyor',
      });
    },
    [downloadWithProgress, t],
  );

  // modeSelector moved to footerStartSlot (grid bottom-left, next to pagination)

  // Fullscreen is now handled internally by EntityGridTemplate (grid-scoped, not page-scoped)

  const handleRetry = useCallback(() => {
    setGridState('idle');
    setRetryKey((current) => current + 1);
  }, [setGridState]);

  const blockedStateContent = useMemo(() => {
    if (!accessProbeReady && dataSourceMode === 'server') {
      return (
        <div className="flex min-h-[320px] items-center justify-center rounded-3xl border border-border-subtle bg-surface-default p-6 shadow-xs">
          <span className="inline-flex h-6 w-6 animate-spin rounded-full border-2 border-border-subtle border-t-action-primary" />
        </div>
      );
    }

    if (gridAccessState === 'idle') {
      return null;
    }

    const description =
      gridAccessState === 'unauthorized'
        ? 'Kullanıcı verilerini görmek için yetkiniz bulunmuyor.'
        : gridAccessState === 'profile-missing'
          ? 'Profiliniz henüz oluşturulmamış. Lütfen sistem yöneticisiyle iletişime geçin.'
          : 'Kullanıcı verileri alınamadı. Lütfen bağlantınızı kontrol edip yeniden deneyin.';

    return (
      <div className="flex min-h-[320px] items-center justify-center rounded-3xl border border-border-subtle bg-surface-default p-6 shadow-xs">
        <div className="flex max-w-xl flex-col items-center gap-4 text-center">
          <Empty description={description} />
          {gridAccessState === 'network-error' ? (
            <Button type="button" onClick={handleRetry}>
              Yeniden dene
            </Button>
          ) : null}
        </div>
      </div>
    );
  }, [accessProbeReady, dataSourceMode, gridAccessState, handleRetry]);

  return (
    blockedStateContent ?? (
      <React.Suspense fallback={<div style={{ height: 320 }} />}>
        <EntityGridTemplate<UserSummary>
          key={retryKey}
          gridId={GRID_VARIANT_ID}
          gridSchemaVersion={GRID_VARIANT_SCHEMA_VERSION}
          columnDefs={columnDefs}
          gridOptions={gridOptions}
          exportConfig={exportConfig}
          onRowDoubleClick={onSelectUser}
          isFullscreen={isFullscreen}
          dataSourceMode={dataSourceMode}
          rowData={dataSourceMode === 'client' ? clientRows : undefined}
          total={dataSourceMode === 'client' ? clientRows.length : undefined}
          createServerSideDatasource={dataSourceMode === 'server' ? createServerSideDatasource : undefined}
          onGridReady={handleGridReady}
          footerStartSlot={modeSelector}
          onServerExport={dataSourceMode === 'server' ? handleServerExport : undefined}
          themeLabel={t('users.grid.themeLabel')}
          quickFilterLabel={t('users.grid.quickFilterLabel')}
          variantLabel={t('users.grid.variantLabel')}
          quickFilterPlaceholder={t('users.grid.quickFilterPlaceholder')}
          fullscreenTooltip={t('users.grid.fullscreenTooltip')}
          resetFiltersLabel={t('users.grid.toolbar.resetFilters')}
          localeText={localeText}
        />
      </React.Suspense>
    )
  );
};

export default UsersGrid;
