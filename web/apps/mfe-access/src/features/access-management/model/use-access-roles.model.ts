import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import type { AccessFilters, AccessLevel, AccessModulePolicy, AccessRole } from './access.types';
import {
  getRoles,
  getRole,
  updateRole,
  UpdateRoleRequestDto,
  createRole as createRoleApi,
  cloneRole as cloneRoleApi,
  deleteRole as deleteRoleApi,
  updateRolePermissions,
} from '../../../entities/roles/api/roles.api';
import { pushToast } from '../../../shared/notifications';

const normalise = (value: string) => value.trim().toLowerCase();
const CURRENT_ACTOR = 'shell.user';

const createAuditId = (prefix: string) => {
  if (typeof globalThis.crypto !== 'undefined' && typeof globalThis.crypto.randomUUID === 'function') {
    return `${prefix}-${globalThis.crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
};

const clonePolicy = (policy: AccessModulePolicy, actor: string, timestamp: string): AccessModulePolicy => ({
  ...policy,
  lastUpdatedAt: timestamp,
  updatedBy: actor
});

const slugify = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
    .slice(0, 32);

export interface CloneRolePayload {
  sourceRoleId: string;
  name: string;
  description?: string;
  copyMemberCount?: boolean;
}

export interface BulkUpdatePayload {
  roleIds: string[];
  moduleKey: string;
  moduleLabel: string;
  level: AccessLevel;
}

export interface CloneRoleResult {
  role: AccessRole;
  auditId: string;
}

export interface BulkUpdateResult {
  updatedRoleIds: string[];
  auditId: string;
}

export const useAccessRoles = (filters: AccessFilters) => {
  const [data, setData] = React.useState<AccessRole[]>([]);
  const queryClient = useQueryClient();

  const rolesQuery = useQuery({
    queryKey: ['roles'],
    queryFn: getRoles,
    staleTime: 30_000,
  });

  React.useEffect(() => {
    if (Array.isArray(rolesQuery.data?.items) && rolesQuery.data.items.length > 0) {
      setData(rolesQuery.data.items);
      return;
    }
    if (rolesQuery.status === 'error') {
      if (process.env.NODE_ENV !== 'production') console.warn('[useAccessRoles] Role listesi alınamadı.', rolesQuery.error);
      /* Error state — let component render error UI instead of silent mock */
    }
  }, [rolesQuery.data, rolesQuery.error, rolesQuery.status]);

  const fetchRoleDetail = React.useCallback(
    async (id: string) => {
      try {
        return await queryClient.ensureQueryData(['role', id], () => getRole(id));
      } catch (error: unknown) {
        if (process.env.NODE_ENV !== 'production') console.warn('[useAccessRoles] Role detayı alınamadı.', error);
        throw error; /* Propagate to React Query error state */
      }
    },
    [queryClient],
  );

  const roleUpdateMutation = useMutation({
    mutationFn: (vars: { id: string; payload: UpdateRoleRequestDto }) => updateRole(vars.id, vars.payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['roles'] });
      await queryClient.invalidateQueries({ queryKey: ['role'] });
    },
    onError: (error: Error) => {
      pushToast('error', error.message);
    },
  });

  const createRoleMutation = useMutation({
    mutationFn: (payload: { name: string; description?: string }) => createRoleApi(payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['roles'] });
    },
    onError: (error: Error) => {
      pushToast('error', error.message);
    },
  });

  const deleteRoleMutation = useMutation({
    mutationFn: (roleId: string) => deleteRoleApi(roleId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['roles'] });
    },
    onError: (error: Error) => {
      pushToast('error', error.message);
    },
  });

  const roleCloneMutation = useMutation({
    mutationFn: (payload: CloneRolePayload) => cloneRoleApi(payload.sourceRoleId, payload),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['roles'] });
    },
    onError: (error: Error) => {
      pushToast('error', error.message);
    },
  });

  const roles = React.useMemo(() => {
    return data.filter((role) => {
      const matchesSearch =
        filters.search.length === 0 ||
        normalise(role.name).includes(normalise(filters.search)) ||
        normalise(role.description ?? '').includes(normalise(filters.search));

      const matchesModule =
        filters.moduleKey === 'ALL' ||
        role.policies.some((policy) => policy.moduleKey === filters.moduleKey);

      const matchesLevel =
        filters.level === 'ALL' ||
        role.policies.some((policy) => policy.level === filters.level);

      return matchesSearch && matchesModule && matchesLevel;
    });
  }, [data, filters.level, filters.moduleKey, filters.search]);

  const modules = React.useMemo(() => {
    const entries = new Map<string, string>();
    data.forEach((role) => {
      role.policies.forEach((policy) => {
        if (!entries.has(policy.moduleKey)) {
          entries.set(policy.moduleKey, policy.moduleLabel);
        }
      });
    });
    return entries;
  }, [data]);

  const cloneRole = React.useCallback(
    async (payload: CloneRolePayload): Promise<CloneRoleResult> => {
      try {
        if (!/^\d+$/.test(payload.sourceRoleId)) {
          throw new Error(`Mock role kaynağı backend clone için uygun değil: ${payload.sourceRoleId}`);
        }
        const cloned = await roleCloneMutation.mutateAsync(payload);
        await queryClient.invalidateQueries({ queryKey: ['roles'] });
        return { role: cloned.role, auditId: cloned.auditId ?? cloned.role.id };
      } catch (error: unknown) {
        console.warn('[useAccessRoles] Role klonlama başarısız, mock fallback.', error);
        const source = data.find((role) => role.id === payload.sourceRoleId);
        if (!source) {
          throw new Error(`Rol bulunamadı: ${payload.sourceRoleId}`);
        }
        const timestamp = new Date().toISOString();
        const slug = slugify(payload.name);
        const auditId = createAuditId('audit-clone');
        const clonedPolicies = source.policies.map((policy) => clonePolicy(policy, CURRENT_ACTOR, timestamp));
        const newRole: AccessRole = {
          ...source,
          id: `role-${slug || 'clone'}-${Date.now().toString(36)}`,
          name: payload.name,
          description: payload.description ?? source.description,
          memberCount: payload.copyMemberCount ? source.memberCount : 0,
          isSystemRole: false,
          policies: clonedPolicies,
          lastModifiedAt: timestamp,
          lastModifiedBy: CURRENT_ACTOR
        };
        setData((prev) => [newRole, ...prev]);
        return { role: newRole, auditId };
      }
    },
    [data, queryClient, roleCloneMutation]
  );

  const bulkUpdateRoles = React.useCallback(
    (payload: BulkUpdatePayload, actor: string = CURRENT_ACTOR): BulkUpdateResult => {
      const timestamp = new Date().toISOString();
      const targetSet = new Set(payload.roleIds);
      if (targetSet.size === 0) {
        return { updatedRoleIds: [], auditId: createAuditId('audit-bulk-skip') };
      }

      const auditId = createAuditId('audit-bulk');
      const updatedRoleIds: string[] = [];

      setData((prev) =>
        prev.map((role) => {
          if (!targetSet.has(role.id)) {
            return role;
          }

          let changed = false;
          const policies = role.policies.map((policy) => {
            if (policy.moduleKey !== payload.moduleKey) {
              return policy;
            }
            if (policy.level === payload.level) {
              return policy;
            }
            changed = true;
            return {
              ...policy,
              level: payload.level,
              lastUpdatedAt: timestamp,
              updatedBy: actor
            };
          });

          if (!policies.some((policy) => policy.moduleKey === payload.moduleKey)) {
            changed = true;
            policies.push({
              moduleKey: payload.moduleKey,
              moduleLabel: payload.moduleLabel,
              level: payload.level,
              lastUpdatedAt: timestamp,
              updatedBy: actor
            });
          }

          if (!changed) {
            return role;
          }

          updatedRoleIds.push(role.id);

          return {
            ...role,
            policies,
            lastModifiedAt: timestamp,
            lastModifiedBy: actor
          };
        })
      );

      return {
        updatedRoleIds,
        auditId
      };
    },
    []
  );

  return {
    roles,
    total: roles.length,
    modules,
    cloneRole,
    bulkUpdateRoles,
    fetchRoleDetail,
    roleUpdateMutation,
    createRoleMutation,
    deleteRoleMutation,
    roleCloneMutation,
    updateRolePermissionsMutation: useMutation({
      mutationFn: (vars: { id: string; permissionIds: string[] }) =>
        updateRolePermissions(vars.id, { permissionIds: vars.permissionIds }),
      onSuccess: async (_data, vars) => {
        await queryClient.invalidateQueries({ queryKey: ['roles'] });
        await queryClient.invalidateQueries({ queryKey: ['role', vars.id] });
      },
      onError: (error: Error) => {
        pushToast('error', error.message);
      },
    }),
  };
};
