import React, { useState, useMemo } from 'react';
import type { Meta, StoryObj } from '@storybook/react-webpack5';
import { PermissionProvider } from '../packages/auth/src/PermissionProvider';
import { useZanzibarAccess } from '../packages/auth/src/useZanzibarAccess';
import type { AuthzMeResponse, ZanzibarAccessLevel } from '../packages/auth/src/types';

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const BASE_AUTHZ: AuthzMeResponse = {
  userId: 'demo-user',
  superAdmin: false,
  allowedModules: ['AUDIT', 'REPORT'],
  allowedCompanyIds: [1],
  allowedProjectIds: [],
  allowedWarehouseIds: [],
  roles: ['DemoRole'],
  modules: { AUDIT: 'VIEW', REPORT: 'VIEW' },
  actions: { EXPORT_PDF: 'ALLOW', DELETE_RECORD: 'DENY' },
  reports: { HR_REPORTS: 'ALLOW', FINANCE_REPORTS: 'DENY' },
  scopes: { companyIds: [1] },
  authzVersion: 1,
};

const SUPER_ADMIN_AUTHZ: AuthzMeResponse = {
  ...BASE_AUTHZ,
  userId: 'admin-user',
  superAdmin: true,
  roles: ['SuperAdmin'],
  modules: { AUDIT: 'MANAGE', REPORT: 'MANAGE' },
};

function mockHttpGet(authz: AuthzMeResponse) {
  return async () => ({ data: authz });
}

// ---------------------------------------------------------------------------
// Shared UI helpers
// ---------------------------------------------------------------------------

function AccessLevelBadge({ level }: { level: ZanzibarAccessLevel }) {
  const styles: Record<ZanzibarAccessLevel, string> = {
    full: 'bg-green-100 text-green-800 border-green-300',
    readonly: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    disabled: 'bg-red-100 text-red-800 border-red-300',
    hidden: 'bg-gray-100 text-gray-500 border-gray-300',
  };
  return (
    <span className={`inline-block rounded border px-2 py-0.5 text-xs font-medium ${styles[level]}`}>
      {level}
    </span>
  );
}

function DebugPanel({
  access,
  loading,
  reason,
  relation,
  objectType,
  objectId,
}: {
  access: ZanzibarAccessLevel;
  loading: boolean;
  reason: string;
  relation: string;
  objectType: string;
  objectId: string;
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 font-mono text-xs">
      <div className="mb-2 font-sans text-xs font-medium text-gray-500">Hook Return Value</div>
      <div className="space-y-1.5">
        <div className="flex items-center gap-2">
          <span className="w-16 text-gray-400">access:</span>
          <AccessLevelBadge level={access} />
        </div>
        <div className="flex items-center gap-2">
          <span className="w-16 text-gray-400">loading:</span>
          <span className={loading ? 'text-blue-600' : 'text-gray-600'}>{String(loading)}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-16 text-gray-400">reason:</span>
          <span className="rounded bg-gray-200 px-1.5 py-0.5 text-gray-700">{reason}</span>
        </div>
      </div>
      <div className="mt-3 border-t border-gray-200 pt-2 text-gray-400">
        <div>relation: {relation}</div>
        <div>objectType: {objectType}</div>
        <div>objectId: {objectId}</div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Internal story components (hooks can only be called inside React components)
// ---------------------------------------------------------------------------

/**
 * Wrapper that renders useZanzibarAccess result in a debug panel.
 * This is needed because hooks cannot be called at story level.
 */
function HookDebugDisplay({
  relation,
  objectType,
  objectId,
  httpPost,
}: {
  relation: string;
  objectType: string;
  objectId: string;
  httpPost?: (url: string, body: any) => Promise<{ data: any }>;
}) {
  const { access, loading, reason } = useZanzibarAccess(relation, objectType, objectId, httpPost);

  return (
    <DebugPanel
      access={access}
      loading={loading}
      reason={reason}
      relation={relation}
      objectType={objectType}
      objectId={objectId}
    />
  );
}

function InteractiveHookDemo({ authz }: { authz: AuthzMeResponse }) {
  const [relation, setRelation] = useState('can_view');
  const [objectType, setObjectType] = useState('report');
  const [objectId, setObjectId] = useState('HR_REPORTS');
  const [serverAllowed, setServerAllowed] = useState(true);
  const [serverReason, setServerReason] = useState('granted');

  const httpPost = useMemo(
    () => async () => ({ data: { allowed: serverAllowed, reason: serverReason } }),
    [serverAllowed, serverReason],
  );

  return (
    <div className="w-[560px] space-y-4">
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <div className="mb-3 text-xs font-medium text-gray-500">Parameters</div>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="mb-1 block text-xs text-gray-400">relation</label>
            <select
              value={relation}
              onChange={(e) => setRelation(e.target.value)}
              className="w-full rounded border border-gray-300 p-1.5 text-xs"
            >
              <option value="can_view">can_view</option>
              <option value="can_edit">can_edit</option>
              <option value="can_manage">can_manage</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-400">objectType</label>
            <select
              value={objectType}
              onChange={(e) => setObjectType(e.target.value)}
              className="w-full rounded border border-gray-300 p-1.5 text-xs"
            >
              <option value="report">report</option>
              <option value="module">module</option>
              <option value="action">action</option>
              <option value="company">company</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-400">objectId</label>
            <input
              value={objectId}
              onChange={(e) => setObjectId(e.target.value)}
              className="w-full rounded border border-gray-300 p-1.5 text-xs"
            />
          </div>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs text-gray-400">Server: allowed</label>
            <select
              value={String(serverAllowed)}
              onChange={(e) => setServerAllowed(e.target.value === 'true')}
              className="w-full rounded border border-gray-300 p-1.5 text-xs"
            >
              <option value="true">true</option>
              <option value="false">false</option>
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-gray-400">Server: reason</label>
            <select
              value={serverReason}
              onChange={(e) => setServerReason(e.target.value)}
              className="w-full rounded border border-gray-300 p-1.5 text-xs"
            >
              <option value="granted">granted</option>
              <option value="blocked">blocked</option>
              <option value="no_relation">no_relation</option>
              <option value="not_found">not_found</option>
              <option value="error">error</option>
            </select>
          </div>
        </div>
      </div>

      <HookDebugDisplay
        key={`${relation}-${objectType}-${objectId}-${serverAllowed}-${serverReason}`}
        relation={relation}
        objectType={objectType}
        objectId={objectId}
        httpPost={httpPost}
      />
    </div>
  );
}

function AccessLevelMatrixDisplay() {
  const scenarios: Array<{
    relation: string;
    objectType: string;
    objectId: string;
    label: string;
    httpPost?: (url: string, body: any) => Promise<{ data: any }>;
  }> = [
    {
      label: 'SuperAdmin (bypass)',
      relation: 'can_manage',
      objectType: 'module',
      objectId: 'AUDIT',
    },
    {
      label: 'Module VIEW (coarse)',
      relation: 'can_view',
      objectType: 'module',
      objectId: 'AUDIT',
    },
    {
      label: 'Report ALLOW + server granted',
      relation: 'can_view',
      objectType: 'report',
      objectId: 'HR_REPORTS',
      httpPost: async () => ({ data: { allowed: true, reason: 'granted' } }),
    },
    {
      label: 'Report DENY (coarse block)',
      relation: 'can_view',
      objectType: 'report',
      objectId: 'FINANCE_REPORTS',
    },
    {
      label: 'Action ALLOW (coarse)',
      relation: 'can_view',
      objectType: 'action',
      objectId: 'EXPORT_PDF',
    },
    {
      label: 'Module not in list (hidden)',
      relation: 'can_view',
      objectType: 'module',
      objectId: 'WAREHOUSE',
    },
  ];

  return (
    <div className="w-[600px] space-y-3">
      <div className="grid gap-2">
        {scenarios.map((s) => (
          <MatrixRow key={s.label} {...s} />
        ))}
      </div>
    </div>
  );
}

function MatrixRow({
  label,
  relation,
  objectType,
  objectId,
  httpPost,
}: {
  label: string;
  relation: string;
  objectType: string;
  objectId: string;
  httpPost?: (url: string, body: any) => Promise<{ data: any }>;
}) {
  const { access, loading, reason } = useZanzibarAccess(relation, objectType, objectId, httpPost);

  return (
    <div className="flex items-center gap-3 rounded border border-gray-100 bg-white px-3 py-2">
      <div className="min-w-[200px] text-xs text-gray-600">{label}</div>
      <AccessLevelBadge level={access} />
      <span className="rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500">{reason}</span>
      {loading && (
        <div className="h-3 w-3 animate-spin rounded-full border border-blue-300 border-t-blue-600" />
      )}
    </div>
  );
}

function CoarseGateOnlyDisplay() {
  const { access, loading, reason } = useZanzibarAccess('can_view', 'module', 'AUDIT');

  return (
    <div className="w-[480px] space-y-4">
      <div className="rounded-lg border border-blue-100 bg-blue-50 p-3">
        <div className="text-xs font-medium text-blue-800">httpPost not provided</div>
        <p className="mt-1 text-xs text-blue-600">
          httpPost verilmedigi icin yalnizca coarse gate (/me cache) kullanilir.
          Server check atlanir.
        </p>
      </div>
      <DebugPanel
        access={access}
        loading={loading}
        reason={reason}
        relation="can_view"
        objectType="module"
        objectId="AUDIT"
      />
    </div>
  );
}

function ServerCheckFlowDisplay() {
  const httpPost = async () => ({
    data: { allowed: true, reason: 'granted' },
  });
  const { access, loading, reason } = useZanzibarAccess(
    'can_view', 'report', 'HR_REPORTS', httpPost,
  );

  return (
    <div className="w-[480px] space-y-4">
      <div className="rounded-lg border border-green-100 bg-green-50 p-3">
        <div className="text-xs font-medium text-green-800">Full 3-layer flow</div>
        <p className="mt-1 text-xs text-green-600">
          Coarse gate report HR_REPORTS = ALLOW (pass) + server check allowed = true.
          Sonuc: readonly (can_view relation, manage degil).
        </p>
      </div>
      <DebugPanel
        access={access}
        loading={loading}
        reason={reason}
        relation="can_view"
        objectType="report"
        objectId="HR_REPORTS"
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Meta — useZanzibarAccess is a hook, so we use a wrapper component
// ---------------------------------------------------------------------------

const meta: Meta = {
  title: 'Auth/useZanzibarAccess',
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component:
          'Object-level authorization hook. 3 katmanli Zanzibar-Aware yapi: ' +
          '(1) coarse gate /me cache, (2) object-level server check, (3) ZanzibarAccessLevel mapping. ' +
          'Dondu: { access, loading, reason }.',
      },
    },
  },
  tags: ['autodocs'],
};

export default meta;

type Story = StoryObj;

// ---------------------------------------------------------------------------
// Stories
// ---------------------------------------------------------------------------

/**
 * Default: Debug panel showing hook return values for a basic can_view check.
 * Uses coarse gate only (no httpPost).
 */
export const Default: Story = {
  decorators: [
    (Story: React.ComponentType) => (
      <PermissionProvider httpGet={mockHttpGet(BASE_AUTHZ)} initialData={BASE_AUTHZ}>
        <Story />
      </PermissionProvider>
    ),
  ],
  render: () => <CoarseGateOnlyDisplay />,
};

/**
 * SuperAdmin: All checks return full access with reason=superadmin.
 */
export const SuperAdmin: Story = {
  decorators: [
    (Story: React.ComponentType) => (
      <PermissionProvider httpGet={mockHttpGet(SUPER_ADMIN_AUTHZ)} initialData={SUPER_ADMIN_AUTHZ}>
        <Story />
      </PermissionProvider>
    ),
  ],
  render: () => {
    const { access, loading, reason } = useZanzibarAccess('can_manage', 'module', 'ANYTHING');

    return (
      <div className="w-[480px] space-y-4">
        <div className="rounded-lg border border-purple-100 bg-purple-50 p-3">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-purple-800">SuperAdmin Mode</span>
            <span className="rounded bg-purple-200 px-1.5 py-0.5 text-xs text-purple-700">
              bypass
            </span>
          </div>
          <p className="mt-1 text-xs text-purple-600">
            superAdmin = true oldugunda tum kontroller bypass edilir.
            Herhangi bir relation/objectType/objectId icin full donus yapilir.
          </p>
        </div>
        <DebugPanel
          access={access}
          loading={loading}
          reason={reason}
          relation="can_manage"
          objectType="module"
          objectId="ANYTHING"
        />
      </div>
    );
  },
};

/**
 * ServerCheckFlow: Full 3-layer check with server call.
 * Coarse gate passes, server check returns granted.
 */
export const ServerCheckFlow: Story = {
  decorators: [
    (Story: React.ComponentType) => (
      <PermissionProvider httpGet={mockHttpGet(BASE_AUTHZ)} initialData={BASE_AUTHZ}>
        <Story />
      </PermissionProvider>
    ),
  ],
  render: () => <ServerCheckFlowDisplay />,
};

/**
 * Interactive: Change relation/objectType/objectId and server response
 * to see how the hook resolves access level in real-time.
 */
export const Interactive: Story = {
  decorators: [
    (Story: React.ComponentType) => (
      <PermissionProvider httpGet={mockHttpGet(BASE_AUTHZ)} initialData={BASE_AUTHZ}>
        <Story />
      </PermissionProvider>
    ),
  ],
  render: () => <InteractiveHookDemo authz={BASE_AUTHZ} />,
};

/**
 * AccessLevelMatrix: Side-by-side comparison of all access levels
 * across different relation/objectType/objectId combinations.
 */
export const AccessLevelMatrix: Story = {
  decorators: [
    (Story: React.ComponentType) => (
      <PermissionProvider httpGet={mockHttpGet(BASE_AUTHZ)} initialData={BASE_AUTHZ}>
        <Story />
      </PermissionProvider>
    ),
  ],
  render: () => <AccessLevelMatrixDisplay />,
};

/**
 * SuperAdminMatrix: Same matrix but with superAdmin=true.
 * All rows should show full access.
 */
export const SuperAdminMatrix: Story = {
  decorators: [
    (Story: React.ComponentType) => (
      <PermissionProvider httpGet={mockHttpGet(SUPER_ADMIN_AUTHZ)} initialData={SUPER_ADMIN_AUTHZ}>
        <Story />
      </PermissionProvider>
    ),
  ],
  render: () => <AccessLevelMatrixDisplay />,
};
