import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { UserDetail } from '@mfe/shared-types';
import { useUserMutations } from '../../../features/user-management/model/use-users-query.model';
import { PERMISSIONS } from '../../../features/user-management/lib/permissions.constants';
import { useAuthorization } from '../../../features/user-management/model/use-authorization.model';
import { DetailDrawer, Tabs, Checkbox, Button, Badge } from '@mfe/design-system';
import { useUsersI18n } from '../../../i18n/useUsersI18n';
import { pushToast } from '../../../shared/notifications';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@mfe/shared-http';

const badgeBaseClass =
  'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold leading-tight';
const badgeToneClass: Record<string, string> = {
  default: 'border-border-subtle bg-surface-muted text-text-secondary',
  blue: 'border-state-info-border bg-state-info text-state-info-text',
  success: 'border-state-success-border bg-state-success-bg text-state-success-text',
  warning: 'border-state-warning-border bg-state-warning-bg text-state-warning-text',
  error: 'border-state-danger-border bg-state-danger-bg text-state-danger-text',
};
const getBadgeClass = (tone: string) => `${badgeBaseClass} ${badgeToneClass[tone] ?? badgeToneClass.default}`;

interface UserDetailDrawerProps {
  open: boolean;
  onClose: () => void;
  user: UserDetail | null;
}

// --- Role & Scope types ---
interface RoleOption { id: number; name: string; }
interface ScopeEntity { id: number; name: string; }

const FALLBACK_ROLE_OPTIONS: RoleOption[] = [
  { id: 1, name: 'ADMIN' },
  { id: 2, name: 'USER_MANAGER' },
  { id: 3, name: 'USER_VIEWER' },
  { id: 4, name: 'PURCHASE_MANAGER' },
  { id: 5, name: 'WAREHOUSE_OPERATOR' },
];

const FALLBACK_ROLE_ID_BY_NAME: Record<string, number> = FALLBACK_ROLE_OPTIONS.reduce<Record<string, number>>((acc, role) => {
  acc[role.name] = role.id;
  return acc;
}, {});

const resolveFallbackRoleOptions = (currentRole: string | undefined): RoleOption[] => {
  const normalizedRole = String(currentRole ?? '').trim().toUpperCase();
  if (!normalizedRole || FALLBACK_ROLE_ID_BY_NAME[normalizedRole]) {
    return FALLBACK_ROLE_OPTIONS;
  }
  return [...FALLBACK_ROLE_OPTIONS, { id: FALLBACK_ROLE_OPTIONS.length + 1, name: normalizedRole }];
};

const UserDetailDrawer: React.FC<UserDetailDrawerProps> = ({ open, onClose, user }) => {
  const { t, locale } = useUsersI18n();
  const queryClient = useQueryClient();
  const { hasPermission, userId: currentUserId, role: currentRole } = useAuthorization();
  const isAdmin = currentRole?.toUpperCase() === 'ADMIN';
  const canEdit = hasPermission('EDIT_USERS') || hasPermission(PERMISSIONS.USER_MANAGEMENT_EDIT);

  const storedScope = useMemo(() => {
    try {
      const raw = typeof window !== 'undefined' ? window.localStorage.getItem('halo.scope') : null;
      return raw ? JSON.parse(raw) : {};
    } catch { return {}; }
  }, []);

  const { toggleStatusMutation, updateSessionTimeoutMutation } = useUserMutations({
    companyId: storedScope.companyId,
    projectId: storedScope.projectId,
    warehouseId: storedScope.warehouseId,
  });

  // --- State ---
  const [selectedRoleIds, setSelectedRoleIds] = useState<number[]>([]);
  const [selectedCompanyIds, setSelectedCompanyIds] = useState<number[]>([]);
  const [selectedProjectIds, setSelectedProjectIds] = useState<number[]>([]);
  const [selectedWarehouseIds, setSelectedWarehouseIds] = useState<number[]>([]);
  const [selectedBranchIds, setSelectedBranchIds] = useState<number[]>([]);
  const [sessionTimeoutMinutes, setSessionTimeoutMinutes] = useState<number>(15);
  const [dirty, setDirty] = useState(false);

  // --- Queries ---
  const rolesQuery = useQuery({
    queryKey: ['roles-list'],
    queryFn: async () => {
      try {
        const res = await api.get('/api/v1/roles');
        const data = res.data as any;
        const items = data?.items ?? data?.content ?? data ?? [];
        return (Array.isArray(items) ? items : []).map((r: any) => ({ id: r.id, name: r.name })) as RoleOption[];
      } catch {
        return resolveFallbackRoleOptions(user?.role);
      }
    },
    enabled: open,
  });

  const userRolesQuery = useQuery({
    queryKey: ['user-roles', user?.id],
    queryFn: async () => {
      try {
        const res = await api.get(`/api/v1/authz/users/${user!.id}/roles`);
        return (res.data as any[]).map((r: any) => r.roleId as number);
      } catch {
        const fallbackRoleId = FALLBACK_ROLE_ID_BY_NAME[String(user?.role ?? '').trim().toUpperCase()];
        return fallbackRoleId ? [fallbackRoleId] : [];
      }
    },
    enabled: open && !!user,
  });

  // Reset state when user changes
  useEffect(() => {
    if (userRolesQuery.data) {
      setSelectedRoleIds(userRolesQuery.data);
    }
    setSessionTimeoutMinutes(user?.sessionTimeoutMinutes ?? 15);
    setDirty(false);
    // Scope initial values would come from user data or assignments
    setSelectedCompanyIds([]);
    setSelectedProjectIds([]);
    setSelectedWarehouseIds([]);
    setSelectedBranchIds([]);
  }, [user?.id, userRolesQuery.data]);

  // --- Mutations ---
  const assignMutation = useMutation({
    mutationFn: async () => {
      await api.post(`/api/v1/authz/users/${user!.id}/assignments`, {
        roleIds: selectedRoleIds,
        scopes: {
          companyIds: selectedCompanyIds,
          projectIds: selectedProjectIds,
          warehouseIds: selectedWarehouseIds,
          branchIds: selectedBranchIds,
        },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] });
      queryClient.invalidateQueries({ queryKey: ['user-roles', user?.id] });
      pushToast('success', t('users.detail.assignmentSaved'));
      setDirty(false);
    },
    onError: (err: Error) => pushToast('error', err.message),
  });

  const handleSave = () => assignMutation.mutate();

  const toggleRole = (roleId: number) => {
    setSelectedRoleIds(prev =>
      prev.includes(roleId) ? prev.filter(id => id !== roleId) : [...prev, roleId]
    );
    setDirty(true);
  };

  const toggleScope = (
    setter: React.Dispatch<React.SetStateAction<number[]>>,
    id: number,
  ) => {
    setter(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
    setDirty(true);
  };

  // --- Session timeout ---
  const handleSessionTimeoutSave = async () => {
    if (!user) return;
    const nextValue = Math.round(Number(sessionTimeoutMinutes));
    if (!Number.isFinite(nextValue) || nextValue < 1) {
      pushToast('warning', t('users.detail.sessionTimeout.minWarning'));
      return;
    }
    if (user.sessionTimeoutMinutes === nextValue) return;
    try {
      await updateSessionTimeoutMutation.mutateAsync({ userId: user.id, sessionTimeoutMinutes: nextValue });
      pushToast('success', t('users.detail.sessionTimeout.updated'));
    } catch { pushToast('error', t('users.detail.sessionTimeout.updateFailed')); }
  };

  const formattedLastLogin = useMemo(() => {
    if (!user?.lastLoginAt) return t('shell.header.neverLoggedIn');
    try {
      const date = new Date(user.lastLoginAt);
      const localeMap: Record<string, string> = { tr: 'tr-TR', en: 'en-US', de: 'de-DE', es: 'es-ES' };
      return date.toLocaleString(localeMap[locale] ?? undefined);
    } catch { return String(user?.lastLoginAt ?? ''); }
  }, [user?.lastLoginAt, locale, t]);

  const statusToneMap: Record<string, string> = {
    ACTIVE: 'success', INACTIVE: 'default', INVITED: 'warning', SUSPENDED: 'error',
  };

  if (!user) return null;

  const roles = rolesQuery.data ?? [];

  // Placeholder scope data — in production these come from core-data-service
  const companies: ScopeEntity[] = [
    { id: 1, name: 'Serban Holding' },
    { id: 2, name: 'Acme Corp' },
    { id: 3, name: 'Beta Ltd' },
  ];
  const projects: ScopeEntity[] = [
    { id: 1, name: 'Proje Alpha' },
    { id: 2, name: 'Proje Beta' },
  ];
  const warehouses: ScopeEntity[] = [
    { id: 1, name: 'İstanbul Depo' },
    { id: 2, name: 'Ankara Depo' },
  ];
  const branches: ScopeEntity[] = [
    { id: 1, name: 'İstanbul Şube' },
    { id: 2, name: 'Ankara Şube' },
  ];

  const scopeCheckboxList = (items: ScopeEntity[], selected: number[], setter: React.Dispatch<React.SetStateAction<number[]>>) => (
    <div className="flex flex-col gap-2 mt-2">
      {items.map(item => (
        <Checkbox
          key={item.id}
          label={item.name}
          checked={selected.includes(item.id)}
          onChange={() => toggleScope(setter, item.id)}
          disabled={!canEdit}
        />
      ))}
    </div>
  );

  const scopeTabs = [
    { key: 'companies', label: 'Şirketler', content: scopeCheckboxList(companies, selectedCompanyIds, setSelectedCompanyIds) },
    { key: 'projects', label: 'Projeler', content: scopeCheckboxList(projects, selectedProjectIds, setSelectedProjectIds) },
    { key: 'warehouses', label: 'Depolar', content: scopeCheckboxList(warehouses, selectedWarehouseIds, setSelectedWarehouseIds) },
    { key: 'branches', label: 'Şubeler', content: scopeCheckboxList(branches, selectedBranchIds, setSelectedBranchIds) },
  ];

  return (
    <DetailDrawer
      open={open}
      onClose={onClose}
      width={520}
      title={`${user.fullName}`}
      extra={
        <button type="button" onClick={onClose} className="text-sm font-semibold text-text-secondary hover:text-text-primary">
          {t('shell.launcher.close')}
        </button>
      }
    >
      <div className="flex flex-col gap-6">
        {/* Profile Section */}
        <section>
          <h3 className="text-base font-semibold text-text-primary">{t('users.detail.section.profile')}</h3>
          <dl className="flex flex-col mt-3 gap-3 rounded-2xl border border-border-subtle bg-surface-muted p-4 text-sm">
            <div className="flex items-start justify-between gap-4">
              <dt className="text-xs font-semibold uppercase tracking-wide text-text-subtle">{t('users.grid.columns.email')}</dt>
              <dd className="text-text-primary">{user.email}</dd>
            </div>
            <div className="flex items-start justify-between gap-4">
              <dt className="text-xs font-semibold uppercase tracking-wide text-text-subtle">{t('users.grid.columns.status')}</dt>
              <dd className="flex items-center gap-3">
                <span className={getBadgeClass(statusToneMap[user.status] ?? 'default')}>{user.status}</span>
                {canEdit && (
                  <button
                    type="button" role="switch" aria-checked={user.status === 'ACTIVE'}
                    disabled={toggleStatusMutation.isPending}
                    onClick={async () => {
                      try {
                        const nextEnabled = user.status !== 'ACTIVE';
                        await toggleStatusMutation.mutateAsync({ userId: user.id, enabled: nextEnabled });
                        pushToast('success', t('users.actions.status.success'));
                      } catch (e: unknown) { pushToast('error', (e as Error).message); }
                    }}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${user.status === 'ACTIVE' ? 'bg-action-primary' : 'bg-border-subtle'}`}
                  >
                    <span className="inline-block h-5 w-5 transform rounded-full bg-surface-default transition"
                      style={{ transform: user.status === 'ACTIVE' ? 'translateX(20px)' : 'translateX(2px)' }} />
                  </button>
                )}
              </dd>
            </div>
            <div className="flex items-start justify-between gap-4">
              <dt className="text-xs font-semibold uppercase tracking-wide text-text-subtle">{t('users.grid.columns.sessionTimeoutMinutes')}</dt>
              <dd>
                {canEdit ? (
                  <div className="flex items-center gap-2">
                    <input type="number" min={1} max={1440} value={sessionTimeoutMinutes}
                      onChange={e => setSessionTimeoutMinutes(Number(e.target.value))}
                      className="w-20 rounded-xl border border-border-subtle px-3 py-1.5 text-sm" />
                    <button type="button" onClick={handleSessionTimeoutSave}
                      disabled={updateSessionTimeoutMutation.isPending || sessionTimeoutMinutes === (user.sessionTimeoutMinutes ?? 15)}
                      className="rounded-xl bg-action-primary px-3 py-1.5 text-xs font-semibold text-action-primary-text disabled:opacity-50">
                      {updateSessionTimeoutMutation.isPending ? '...' : t('users.detail.sessionTimeout.save')}
                    </button>
                  </div>
                ) : (
                  <span className="text-text-secondary">{user.sessionTimeoutMinutes ?? 15} dk</span>
                )}
              </dd>
            </div>
            <div className="flex items-start justify-between gap-4">
              <dt className="text-xs font-semibold uppercase tracking-wide text-text-subtle">{t('users.grid.columns.lastLoginAt')}</dt>
              <dd className="text-text-secondary">{formattedLastLogin}</dd>
            </div>
          </dl>
        </section>

        <hr className="border-border-subtle" />

        {/* Roles Section — Multi-select checkboxes */}
        <section>
          <h3 className="text-base font-semibold text-text-primary">Roller</h3>
          <p className="text-xs text-text-subtle mt-1">Kullanıcıya birden fazla rol atayabilirsiniz. İzinler rollerin birleşimidir.</p>
          <div className="mt-3 flex flex-col gap-2">
            {rolesQuery.isLoading && <span className="text-xs text-text-subtle">Yükleniyor...</span>}
            {roles.map(role => (
              <Checkbox
                key={role.id}
                label={role.name}
                checked={selectedRoleIds.includes(role.id)}
                onChange={() => toggleRole(role.id)}
                disabled={!canEdit}
              />
            ))}
            {roles.length === 0 && !rolesQuery.isLoading && (
              <span className="text-xs text-text-subtle">Henüz rol tanımlanmamış.</span>
            )}
          </div>
        </section>

        <hr className="border-border-subtle" />

        {/* Scope Section — Tabbed */}
        <section>
          <h3 className="text-base font-semibold text-text-primary">Veri Erişimi</h3>
          <p className="text-xs text-text-subtle mt-1">Scope atanmadan kullanıcı hiçbir veri göremez.</p>
          <div className="mt-3">
            <Tabs items={scopeTabs} variant="line" size="sm" />
          </div>
        </section>

        <hr className="border-border-subtle" />

        {/* Footer — Save */}
        {canEdit && (
          <div className="flex items-center justify-end gap-3">
            <button type="button" onClick={onClose}
              className="rounded-xl border border-border-subtle px-4 py-2 text-sm font-medium text-text-secondary hover:bg-surface-muted">
              Vazgeç
            </button>
            <button type="button" onClick={handleSave}
              disabled={!dirty || assignMutation.isPending}
              className="rounded-xl bg-action-primary px-4 py-2 text-sm font-semibold text-action-primary-text shadow-xs hover:opacity-90 disabled:opacity-50">
              {assignMutation.isPending ? 'Kaydediliyor...' : 'Kaydet'}
            </button>
          </div>
        )}
      </div>
    </DetailDrawer>
  );
};

export default UserDetailDrawer;
