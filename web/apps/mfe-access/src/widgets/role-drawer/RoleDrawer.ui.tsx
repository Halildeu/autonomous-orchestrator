import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Badge, Button, Checkbox, DetailDrawer, Select, Switch, TextInput } from '@mfe/design-system';
import type { AccessRole, AccessLevel } from '../../features/access-management/model/access.types';
import { getPermissions } from '../../entities/permissions/api/permissions.api';
import { api } from '@mfe/shared-http';

interface RoleDrawerProps {
  open: boolean;
  mode: 'view' | 'create';
  role: AccessRole | null;
  onClose: () => void;
  onSavePermissions?: (roleId: string, permissionIds: string[]) => Promise<void>;
  onCreateRole?: (values: { name: string; description?: string }) => Promise<void>;
  savingPermissions?: boolean;
  creatingRole?: boolean;
  t: (key: string, params?: Record<string, unknown>) => string;
  formatNumber: (value: number) => string;
  formatDate: (value: Date | number, options?: Intl.DateTimeFormatOptions) => string;
}

// --- Types for permission catalog ---
interface CatalogModule { key: string; label: string; levels: string[]; }
interface CatalogAction { key: string; label: string; module: string; deniable: boolean; }
interface CatalogReport { key: string; label: string; module: string; }
interface CatalogPage { key: string; label: string; module: string; }
interface Catalog { modules: CatalogModule[]; actions: CatalogAction[]; reports: CatalogReport[]; pages: CatalogPage[]; }
interface RoleMember { userId: number; assignedAt?: string; }
interface Granule { type: string; key: string; grant: string; }

const LEVEL_OPTIONS: AccessLevel[] = ['NONE', 'VIEW', 'MANAGE'];
const levelVariant: Record<string, 'info' | 'warning' | 'error' | 'muted'> = { VIEW: 'info', MANAGE: 'error', NONE: 'muted' };

const isPersistedRoleId = (value: string | undefined) => /^\d+$/.test(String(value ?? ''));

const buildFallbackCatalog = (role: AccessRole | null): Catalog => ({
  modules: (role?.policies ?? []).map((policy) => ({
    key: policy.moduleKey,
    label: policy.moduleLabel,
    levels: ['NONE', 'VIEW', 'MANAGE'],
  })),
  actions: [],
  reports: [],
  pages: [],
});

const RoleDrawer: React.FC<RoleDrawerProps> = ({
  open, mode, role, onClose, onSavePermissions, onCreateRole,
  savingPermissions, creatingRole, t, formatNumber, formatDate,
}) => {
  const queryClient = useQueryClient();
  const [createName, setCreateName] = React.useState('');
  const [createDesc, setCreateDesc] = React.useState('');

  // --- Catalog query ---
  const catalogQuery = useQuery({
    queryKey: ['permission-catalog'],
    queryFn: async () => {
      if (!isPersistedRoleId(role?.id)) {
        return buildFallbackCatalog(role);
      }
      const res = await api.get('/api/v1/authz/catalog');
      return res.data as Catalog;
    },
    enabled: open && mode === 'view',
    staleTime: 120_000,
  });

  // --- Members query ---
  const membersQuery = useQuery({
    queryKey: ['role-members', role?.id],
    queryFn: async () => {
      if (!isPersistedRoleId(role?.id)) {
        return [] as RoleMember[];
      }
      const res = await api.get(`/api/v1/roles/${role!.id}/members`);
      return res.data as RoleMember[];
    },
    enabled: open && mode === 'view' && !!role,
  });

  // --- Granule state ---
  const [moduleGrants, setModuleGrants] = React.useState<Record<string, string>>({});
  const [actionGrants, setActionGrants] = React.useState<Record<string, string>>({});
  const [reportGrants, setReportGrants] = React.useState<Record<string, string>>({});
  const [pageGrants, setPageGrants] = React.useState<Record<string, string>>({});
  const [dirty, setDirty] = React.useState(false);
  const [addUserId, setAddUserId] = React.useState('');

  // Init from role policies on open
  React.useEffect(() => {
    if (!role) return;
    const mods: Record<string, string> = {};
    for (const p of role.policies) { mods[p.moduleKey] = p.level; }
    setModuleGrants(mods);
    setActionGrants({});
    setReportGrants({});
    setPageGrants({});
    setDirty(false);
  }, [role]);

  // --- Save granules mutation ---
  const saveGranulesMutation = useMutation({
    mutationFn: async () => {
      if (!isPersistedRoleId(role?.id)) {
        return;
      }
      const granules: Granule[] = [];
      for (const [key, grant] of Object.entries(moduleGrants)) {
        if (grant !== 'NONE') granules.push({ type: 'module', key, grant });
      }
      for (const [key, grant] of Object.entries(actionGrants)) {
        granules.push({ type: 'action', key, grant });
      }
      for (const [key, grant] of Object.entries(reportGrants)) {
        granules.push({ type: 'report', key, grant });
      }
      for (const [key, grant] of Object.entries(pageGrants)) {
        granules.push({ type: 'page', key, grant });
      }
      await api.put(`/api/v1/roles/${role!.id}/granules`, { permissions: granules });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['roles'] });
      setDirty(false);
    },
  });

  // --- Add member mutation ---
  const addMemberMutation = useMutation({
    mutationFn: async (userId: number) => {
      if (!isPersistedRoleId(role?.id)) {
        return;
      }
      await api.post(`/api/v1/roles/${role!.id}/members`, { userIds: [userId] });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['role-members', role?.id] });
      setAddUserId('');
    },
  });

  // --- Remove member mutation ---
  const removeMemberMutation = useMutation({
    mutationFn: async (userId: number) => {
      if (!isPersistedRoleId(role?.id)) {
        return;
      }
      await api.delete(`/api/v1/roles/${role!.id}/members/${userId}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['role-members', role?.id] }),
  });

  // Reset on mode change
  React.useEffect(() => {
    if (mode === 'create') { setCreateName(''); setCreateDesc(''); }
  }, [mode, open]);

  const handleCreate = async () => {
    if (!onCreateRole || !createName.trim()) return;
    await onCreateRole({ name: createName.trim(), description: createDesc.trim() || undefined });
  };

  // --- Create mode ---
  if (mode === 'create') {
    return (
      <DetailDrawer open={open} onClose={onClose} title={t('access.create.title')} size="lg">
        <div className="flex flex-col gap-5 p-1">
          <TextInput label={t('access.create.nameLabel')} placeholder={t('access.create.namePlaceholder')}
            value={createName} onValueChange={setCreateName} autoFocus fullWidth />
          <TextInput label={t('access.create.descriptionLabel')} placeholder={t('access.create.descriptionPlaceholder')}
            value={createDesc} onValueChange={setCreateDesc} fullWidth />
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="secondary" onClick={onClose}>{t('access.clone.cancelText')}</Button>
            <Button onClick={handleCreate} loading={creatingRole} disabled={createName.trim().length < 3}>{t('access.create.submitText')}</Button>
          </div>
        </div>
      </DetailDrawer>
    );
  }

  if (!role) return null;

  const catalog = catalogQuery.data ?? buildFallbackCatalog(role);
  const members = membersQuery.data ?? [];

  // --- Helpers ---
  const setModule = (key: string, level: string) => {
    setModuleGrants(prev => ({ ...prev, [key]: level }));
    setDirty(true);
  };

  const toggleAction = (key: string, grant: 'ALLOW' | 'DENY') => {
    setActionGrants(prev => {
      const current = prev[key];
      if (current === grant) { const next = { ...prev }; delete next[key]; return next; }
      return { ...prev, [key]: grant };
    });
    setDirty(true);
  };

  const toggleReport = (key: string) => {
    setReportGrants(prev => {
      if (prev[key]) { const next = { ...prev }; delete next[key]; return next; }
      return { ...prev, [key]: 'ALLOW' };
    });
    setDirty(true);
  };

  const togglePage = (key: string) => {
    setPageGrants(prev => {
      if (prev[key]) { const next = { ...prev }; delete next[key]; return next; }
      return { ...prev, [key]: 'ALLOW' };
    });
    setDirty(true);
  };

  return (
    <DetailDrawer
      open={open} onClose={onClose} title={role.name}
      subtitle={role.description || t('access.drawer.noDescription')}
      tags={
        <div className="flex gap-2">
          {role.isSystemRole && <Badge variant="default" size="sm">{t('access.drawer.systemRole')}</Badge>}
          <Badge variant="info" size="sm">{formatNumber(role.memberCount)} {t('access.drawer.members')}</Badge>
          {dirty && <Badge variant="warning" size="sm">{t('access.drawer.unsavedChanges')}</Badge>}
        </div>
      }
      size="lg"
    >
      <div className="flex flex-col gap-5">
        {/* --- MODÜLLER --- */}
        <h3 className="text-sm font-semibold uppercase tracking-wide text-text-subtle">Modüller</h3>
        <div className="flex flex-col gap-2">
          {(catalog?.modules ?? []).map(mod => (
            <div key={mod.key} className="flex items-center justify-between rounded-xl border border-border-subtle bg-surface-muted/50 px-4 py-3">
              <span className="text-sm font-medium text-text-primary">{mod.label}</span>
              <select
                className="rounded-lg border border-border-subtle bg-surface-default px-3 py-1.5 text-sm"
                value={moduleGrants[mod.key] ?? 'NONE'}
                onChange={e => setModule(mod.key, e.target.value)}
              >
                {LEVEL_OPTIONS.map(level => (
                  <option key={level} value={level}>{level === 'NONE' ? '—' : level === 'VIEW' ? 'Oku' : 'Yönet'}</option>
                ))}
              </select>
            </div>
          ))}
        </div>

        <hr className="border-border-subtle" />

        {/* --- AKSİYONLAR --- */}
        <h3 className="text-sm font-semibold uppercase tracking-wide text-text-subtle">Aksiyonlar</h3>
        <div className="flex flex-col gap-2">
          {(catalog?.actions ?? []).map(action => {
            const grant = actionGrants[action.key];
            const isAllow = grant === 'ALLOW';
            const isDeny = grant === 'DENY';
            return (
              <div key={action.key} className="flex items-center justify-between rounded-xl border border-border-subtle bg-surface-muted/50 px-4 py-2">
                <div className="flex flex-col">
                  <span className="text-sm font-medium text-text-primary">{action.label}</span>
                  <span className="text-xs text-text-subtle">{action.module}</span>
                </div>
                <div className="flex items-center gap-3">
                  <Checkbox label="İzin" checked={isAllow} onChange={() => toggleAction(action.key, 'ALLOW')} size="sm" />
                  {action.deniable && (
                    <Checkbox
                      label="Engel"
                      checked={isDeny}
                      onChange={() => toggleAction(action.key, 'DENY')}
                      size="sm"
                      className={isDeny ? 'text-state-danger-text' : ''}
                    />
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <hr className="border-border-subtle" />

        {/* --- RAPORLAR --- */}
        <h3 className="text-sm font-semibold uppercase tracking-wide text-text-subtle">Raporlar</h3>
        <div className="flex flex-col gap-2">
          {(catalog?.reports ?? []).map(report => (
            <Checkbox key={report.key} label={report.label}
              checked={!!reportGrants[report.key]}
              onChange={() => toggleReport(report.key)} size="sm"
              description={report.module} />
          ))}
        </div>

        <hr className="border-border-subtle" />

        {/* --- SAYFALAR --- */}
        <h3 className="text-sm font-semibold uppercase tracking-wide text-text-subtle">Sayfalar</h3>
        <div className="flex flex-col gap-2">
          {(catalog?.pages ?? []).map(page => (
            <Checkbox key={page.key} label={page.label}
              checked={!!pageGrants[page.key]}
              onChange={() => togglePage(page.key)} size="sm"
              description={page.module} />
          ))}
        </div>

        <hr className="border-border-subtle" />

        {/* --- ATANMIŞ KİŞİLER --- */}
        <h3 className="text-sm font-semibold uppercase tracking-wide text-text-subtle">
          Atanmış Kişiler ({members.length})
        </h3>
        <div className="flex flex-col gap-2">
          {members.map(member => (
            <div key={member.userId} className="flex items-center justify-between rounded-xl border border-border-subtle bg-surface-muted/50 px-4 py-2">
              <span className="text-sm text-text-primary">Kullanıcı #{member.userId}</span>
              <button type="button" onClick={() => removeMemberMutation.mutate(member.userId)}
                className="text-xs text-state-danger-text hover:underline">Kaldır</button>
            </div>
          ))}
          {members.length === 0 && <p className="text-xs text-text-subtle">Henüz atanmış kişi yok.</p>}

          {/* Kişi ekle */}
          <div className="flex items-center gap-2 mt-2">
            <input
              type="number" placeholder="Kullanıcı ID" value={addUserId}
              onChange={e => setAddUserId(e.target.value)}
              className="flex-1 rounded-lg border border-border-subtle px-3 py-1.5 text-sm"
            />
            <Button size="sm" onClick={() => { if (addUserId) addMemberMutation.mutate(Number(addUserId)); }}
              loading={addMemberMutation.isPending} disabled={!addUserId}>
              + Kişi Ekle
            </Button>
          </div>
        </div>

        <hr className="border-border-subtle" />

        {/* --- FOOTER --- */}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose}>{t('access.clone.cancelText')}</Button>
          <Button onClick={() => saveGranulesMutation.mutate()} loading={saveGranulesMutation.isPending} disabled={!dirty}>
            {t('common.save')}
          </Button>
        </div>
      </div>
    </DetailDrawer>
  );
};

export default RoleDrawer;
