import React from 'react';
import type { ColDef, GridReadyEvent, GridApi } from 'ag-grid-community';
import { buildColDefs, type ColumnMeta } from '@mfe/design-system/advanced/data-grid';
import { Badge, Button } from '@mfe/design-system';
import type { AccessRole, AccessLevel } from '../../features/access-management/model/access.types';

const EntityGridTemplate = React.lazy(() =>
  import('@mfe/design-system').then((m) => ({ default: m.EntityGridTemplate })),
);

interface RolesGridProps {
  roles: AccessRole[];
  modules: Map<string, string>;
  onSelectRole: (role: AccessRole) => void;
  onCreateRole: () => void;
  onDeleteRole: (roleId: string) => Promise<void>;
  onCloneRole: (role: AccessRole) => Promise<void>;
  t: (key: string, params?: Record<string, unknown>) => string;
  formatNumber: (value: number) => string;
  formatDate: (value: Date | number, options?: Intl.DateTimeFormatOptions) => string;
}

const GRID_ID = 'mfe-access/roles-v2';
const GRID_SCHEMA_VERSION = 1;

const LEVEL_BADGE_VARIANT: Record<string, 'error' | 'warning' | 'info' | 'muted'> = {
  MANAGE: 'error',
  VIEW: 'info',
  NONE: 'muted',
};

const showToast = (type: 'success' | 'error', text: string) => {
  try {
    window.dispatchEvent(new CustomEvent('app:toast', { detail: { type, text } }));
  } catch {
    console[type === 'error' ? 'error' : 'log'](text);
  }
};

const RolesGrid: React.FC<RolesGridProps> = ({
  roles,
  modules,
  onSelectRole,
  onCreateRole,
  onDeleteRole,
  onCloneRole,
  t,
  formatNumber,
  formatDate,
}) => {
  const gridApiRef = React.useRef<GridApi<AccessRole> | null>(null);

  const columnMeta = React.useMemo<ColumnMeta[]>(() => [
    { field: 'name', headerNameKey: 'access.grid.columns.name', columnType: 'bold-text', minWidth: 200 },
    { field: 'memberCount', headerNameKey: 'access.grid.columns.memberCount', columnType: 'number', width: 130 },
  ], []);

  const customColumnDefs = React.useMemo<ColDef<AccessRole>[]>(() => [
    {
      headerName: t('access.grid.columns.moduleSummary'),
      field: 'policies',
      minWidth: 280,
      filter: false,
      sortable: false,
      cellRenderer: ({ data }: { data: AccessRole }) => {
        if (!data?.policies?.length) {
          return <span className="text-sm text-text-subtle">{t('access.filter.level.none')}</span>;
        }
        return (
          <div className="flex flex-wrap gap-1.5 py-1">
            {data.policies.map((policy) => (
              <Badge
                key={policy.moduleKey}
                variant={LEVEL_BADGE_VARIANT[policy.level] ?? 'muted'}
                size="sm"
              >
                {policy.moduleLabel ?? policy.moduleKey}: {t(`access.filter.level.${policy.level.toLowerCase()}`)}
              </Badge>
            ))}
          </div>
        );
      },
    },
    {
      headerName: t('access.grid.columns.lastModified'),
      field: 'lastModifiedAt',
      width: 200,
      valueGetter: ({ data }) => {
        if (!data) return '';
        const ts = formatDate(new Date(data.lastModifiedAt), { dateStyle: 'medium', timeStyle: 'short' });
        return `${data.lastModifiedBy} · ${ts}`;
      },
    },
    {
      headerName: '',
      field: 'id',
      width: 100,
      sortable: false,
      filter: false,
      pinned: 'right',
      cellRenderer: ({ data }: { data: AccessRole }) => {
        if (!data) return null;
        return <RowActions role={data} onClone={onCloneRole} onDelete={onDeleteRole} t={t} />;
      },
    },
  ], [formatDate, onCloneRole, onDeleteRole, t]);

  const localeCode = 'tr-TR';
  const columnDefs = React.useMemo<ColDef<AccessRole>[]>(() => {
    const metaDefs = buildColDefs<AccessRole>(columnMeta, t, localeCode) as ColDef<AccessRole>[];
    return [...metaDefs, ...customColumnDefs];
  }, [columnMeta, customColumnDefs, t]);

  const gridOptions = React.useMemo(() => ({
    cellSelection: true,
    multiSortKey: 'ctrl' as const,
  }), []);

  const toolbarExtra = React.useMemo(() => (
    <Button onClick={onCreateRole} size="sm">
      {t('access.actions.create')}
    </Button>
  ), [onCreateRole, t]);

  return (
    <React.Suspense fallback={<div style={{ height: 400 }} />}>
      <EntityGridTemplate<AccessRole>
        gridId={GRID_ID}
        gridSchemaVersion={GRID_SCHEMA_VERSION}
        columnDefs={columnDefs}
        gridOptions={gridOptions}
        dataSourceMode="client"
        rowData={roles}
        total={roles.length}
        onRowDoubleClick={onSelectRole}
        onGridReady={(event: GridReadyEvent<AccessRole>) => {
          gridApiRef.current = event.api;
        }}
        themeLabel={t('access.grid.themeLabel')}
        quickFilterLabel={t('access.grid.quickFilterLabel')}
        quickFilterPlaceholder={t('access.filter.searchPlaceholder')}
        toolbarExtras={toolbarExtra}
      />
    </React.Suspense>
  );
};

// Inline row actions — three-dot menu
const RowActions: React.FC<{
  role: AccessRole;
  onClone: (role: AccessRole) => Promise<void>;
  onDelete: (roleId: string) => Promise<void>;
  t: (key: string) => string;
}> = ({ role, onClone, onDelete, t }) => {
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        className="rounded-md px-2 py-1 text-text-subtle hover:bg-surface-muted hover:text-text-primary"
        onClick={(e) => { e.stopPropagation(); setOpen(!open); }}
      >
        ···
      </button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 w-40 rounded-xl border border-border-subtle bg-surface-default p-1 shadow-lg">
          <button
            type="button"
            className="flex w-full rounded-lg px-3 py-2 text-left text-sm text-text-secondary hover:bg-surface-muted"
            onClick={async () => {
              setOpen(false);
              try {
                await onClone(role);
                showToast('success', t('access.notifications.cloneSuccess.title'));
              } catch {
                showToast('error', t('access.notifications.cloneError'));
              }
            }}
          >
            {t('access.actions.clone')}
          </button>
          <button
            type="button"
            className="flex w-full rounded-lg px-3 py-2 text-left text-sm text-state-danger-text hover:bg-surface-muted disabled:opacity-50"
            disabled={role.isSystemRole}
            onClick={async () => {
              setOpen(false);
              if (!confirm(t('access.delete.message', { roleName: role.name }))) return;
              try {
                await onDelete(role.id);
                showToast('success', t('access.notifications.deleteSuccess'));
              } catch {
                showToast('error', t('access.notifications.deleteError'));
              }
            }}
          >
            {t('access.actions.delete')}
          </button>
        </div>
      )}
    </div>
  );
};

export default RolesGrid;
