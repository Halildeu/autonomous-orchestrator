import React, { useState } from 'react';
import type { Meta, StoryObj } from '@storybook/react-webpack5';
import { PermissionProvider } from '../packages/auth/src/PermissionProvider';
import { ZanzibarGate } from '../packages/auth/src/ZanzibarGate';
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
  actions: {},
  reports: { HR_REPORTS: 'ALLOW' },
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

const RESTRICTED_AUTHZ: AuthzMeResponse = {
  ...BASE_AUTHZ,
  userId: 'restricted-user',
  superAdmin: false,
  allowedModules: [],
  modules: {},
  reports: { HR_REPORTS: 'DENY' },
};

function mockHttpGet(authz: AuthzMeResponse) {
  return async () => ({ data: authz });
}

function mockHttpPostGranted() {
  return async () => ({ data: { allowed: true, reason: 'granted' } });
}

function mockHttpPostDenied(reason: string = 'no_relation') {
  return async () => ({ data: { allowed: false, reason } });
}

function neverResolve() {
  return () => new Promise<{ data: any }>(() => {});
}

// ---------------------------------------------------------------------------
// Decorators
// ---------------------------------------------------------------------------

function withPermissionProvider(authz: AuthzMeResponse) {
  return (Story: React.ComponentType) => (
    <PermissionProvider httpGet={mockHttpGet(authz)} initialData={authz}>
      <Story />
    </PermissionProvider>
  );
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

function ProtectedDashboard() {
  return (
    <div className="rounded-lg border border-green-200 bg-green-50 p-4">
      <h3 className="text-sm font-semibold text-green-800">HR Reports Dashboard</h3>
      <p className="mt-1 text-xs text-green-600">
        Bu icerik yalnizca yetkilendirilmis kullanicilara gorunur.
      </p>
      <div className="mt-3 grid grid-cols-3 gap-2">
        <div className="rounded bg-white p-2 text-center text-xs">
          <div className="text-lg font-bold text-green-700">247</div>
          <div className="text-gray-500">Aktif Calisan</div>
        </div>
        <div className="rounded bg-white p-2 text-center text-xs">
          <div className="text-lg font-bold text-green-700">18</div>
          <div className="text-gray-500">Bekleyen Izin</div>
        </div>
        <div className="rounded bg-white p-2 text-center text-xs">
          <div className="text-lg font-bold text-green-700">3</div>
          <div className="text-gray-500">Yeni Basvuru</div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Meta
// ---------------------------------------------------------------------------

const meta: Meta<typeof ZanzibarGate> = {
  title: 'Auth/ZanzibarGate',
  component: ZanzibarGate,
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component:
          'Object-level authorization gate. 3 katmanli Zanzibar-Aware yapi: ' +
          'coarse gate (/me cache) + object-level server check. ' +
          'Children yalnizca yetki varsa render edilir.',
      },
    },
  },
  argTypes: {
    relation: {
      control: 'select',
      options: ['can_view', 'can_edit', 'can_manage'],
      description: 'OpenFGA relation to check',
    },
    objectType: {
      control: 'select',
      options: ['report', 'module', 'action', 'company'],
      description: 'OpenFGA object type',
    },
    objectId: {
      control: 'text',
      description: 'OpenFGA object ID',
    },
  },
  tags: ['autodocs'],
};

export default meta;

type Story = StoryObj<typeof ZanzibarGate>;

// ---------------------------------------------------------------------------
// Stories
// ---------------------------------------------------------------------------

/**
 * Default: Authorized user sees the protected content.
 * coarse gate AUDIT module + VIEW = pass.
 */
export const Default: Story = {
  decorators: [withPermissionProvider(BASE_AUTHZ)],
  render: () => (
    <div className="w-[480px]">
      <div className="mb-3">
        <span className="text-xs font-medium text-gray-400">
          relation: can_view | objectType: module | objectId: AUDIT
        </span>
      </div>
      <ZanzibarGate relation="can_view" objectType="module" objectId="AUDIT">
        <ProtectedDashboard />
      </ZanzibarGate>
    </div>
  ),
};

/**
 * WithFallback: Denied user sees the fallback UI instead of nothing.
 * report HR_REPORTS = DENY in restrictedAuthz.
 */
export const WithFallback: Story = {
  decorators: [withPermissionProvider(RESTRICTED_AUTHZ)],
  render: () => (
    <div className="w-[480px]">
      <div className="mb-3">
        <span className="text-xs font-medium text-gray-400">
          relation: can_view | objectType: report | objectId: HR_REPORTS (DENIED)
        </span>
      </div>
      <ZanzibarGate
        relation="can_view"
        objectType="report"
        objectId="HR_REPORTS"
        fallback={
          <div className="rounded-lg border border-red-200 bg-red-50 p-4">
            <h3 className="text-sm font-semibold text-red-800">Erisim Engellendi</h3>
            <p className="mt-1 text-xs text-red-600">
              Bu rapora erisim yetkiniz bulunmuyor. Yetki talebi icin sistem yoneticinize basvurun.
            </p>
            <button
              type="button"
              className="mt-3 rounded border border-red-300 bg-white px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-50"
            >
              Yetki Talep Et
            </button>
          </div>
        }
      >
        <ProtectedDashboard />
      </ZanzibarGate>
    </div>
  ),
};

/**
 * SuperAdmin: superAdmin = true bypasses all gates.
 * Even objectType=module with no explicit entry still passes.
 */
export const SuperAdmin: Story = {
  decorators: [withPermissionProvider(SUPER_ADMIN_AUTHZ)],
  render: () => (
    <div className="w-[480px]">
      <div className="mb-3 flex items-center gap-2">
        <span className="text-xs font-medium text-gray-400">
          relation: can_manage | objectType: module | objectId: WAREHOUSE
        </span>
        <span className="rounded bg-purple-100 px-1.5 py-0.5 text-xs font-medium text-purple-700">
          superAdmin
        </span>
      </div>
      <ZanzibarGate relation="can_manage" objectType="module" objectId="WAREHOUSE">
        <div className="rounded-lg border border-purple-200 bg-purple-50 p-4">
          <h3 className="text-sm font-semibold text-purple-800">Warehouse Management</h3>
          <p className="mt-1 text-xs text-purple-600">
            SuperAdmin tum gate kontrollerini bypass eder. Tam erisim.
          </p>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              className="rounded bg-purple-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-purple-700"
            >
              Depo Ekle
            </button>
            <button
              type="button"
              className="rounded border border-purple-300 bg-white px-3 py-1.5 text-xs font-medium text-purple-700 hover:bg-purple-50"
            >
              Transfer Olustur
            </button>
          </div>
        </div>
      </ZanzibarGate>
    </div>
  ),
};

/**
 * Loading: Shows loadingFallback while async server check is in progress.
 * httpPost never resolves to simulate permanent loading state.
 */
export const Loading: Story = {
  render: () => {
    // Use an authz that passes coarse gate but needs server check
    const authz: AuthzMeResponse = {
      ...BASE_AUTHZ,
      superAdmin: false,
      reports: { HR_REPORTS: 'ALLOW' },
    };
    const httpPostNever = neverResolve();

    return (
      <PermissionProvider httpGet={mockHttpGet(authz)} initialData={authz}>
        <div className="w-[480px]">
          <div className="mb-3">
            <span className="text-xs font-medium text-gray-400">
              relation: can_view | objectType: report | objectId: HR_REPORTS (server check pending)
            </span>
          </div>
          <ZanzibarGate
            relation="can_view"
            objectType="report"
            objectId="HR_REPORTS"
            httpPost={httpPostNever}
            loadingFallback={
              <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
                <div className="flex items-center gap-2">
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-blue-300 border-t-blue-600" />
                  <h3 className="text-sm font-semibold text-blue-800">Yetki Kontrol Ediliyor</h3>
                </div>
                <p className="mt-1 text-xs text-blue-600">
                  Object-level yetki kontrolu yapiliyor, lutfen bekleyin...
                </p>
              </div>
            }
            fallback={
              <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-600">
                Erisim engellendi.
              </div>
            }
          >
            <ProtectedDashboard />
          </ZanzibarGate>
        </div>
      </PermissionProvider>
    );
  },
};

/**
 * ServerCheckGranted: Coarse gate passes, server check returns allowed=true.
 * Demonstrates the full 3-layer flow with successful authorization.
 */
export const ServerCheckGranted: Story = {
  render: () => {
    const authz: AuthzMeResponse = {
      ...BASE_AUTHZ,
      superAdmin: false,
      reports: { HR_REPORTS: 'ALLOW' },
    };

    return (
      <PermissionProvider httpGet={mockHttpGet(authz)} initialData={authz}>
        <div className="w-[480px]">
          <div className="mb-3">
            <span className="text-xs font-medium text-gray-400">
              relation: can_view | objectType: report | objectId: HR_REPORTS (server: allowed)
            </span>
          </div>
          <ZanzibarGate
            relation="can_view"
            objectType="report"
            objectId="HR_REPORTS"
            httpPost={mockHttpPostGranted()}
            loadingFallback={
              <div className="p-3 text-sm text-blue-500">Checking...</div>
            }
          >
            <ProtectedDashboard />
          </ZanzibarGate>
        </div>
      </PermissionProvider>
    );
  },
};

/**
 * ServerCheckDenied: Coarse gate passes but server check returns allowed=false.
 * Demonstrates denied state with blocked reason.
 */
export const ServerCheckDenied: Story = {
  render: () => {
    const authz: AuthzMeResponse = {
      ...BASE_AUTHZ,
      superAdmin: false,
      reports: { HR_REPORTS: 'ALLOW' },
    };

    return (
      <PermissionProvider httpGet={mockHttpGet(authz)} initialData={authz}>
        <div className="w-[480px]">
          <div className="mb-3">
            <span className="text-xs font-medium text-gray-400">
              relation: can_edit | objectType: report | objectId: HR_REPORTS (server: blocked)
            </span>
          </div>
          <ZanzibarGate
            relation="can_edit"
            objectType="report"
            objectId="HR_REPORTS"
            httpPost={mockHttpPostDenied('blocked')}
            fallback={
              <div className="rounded-lg border border-orange-200 bg-orange-50 p-4">
                <h3 className="text-sm font-semibold text-orange-800">Duzenleme Yetkisi Yok</h3>
                <p className="mt-1 text-xs text-orange-600">
                  Bu raporu goruntuleme yetkiniz var, ancak duzenleme yetkiniz bulunmuyor.
                </p>
              </div>
            }
          >
            <ProtectedDashboard />
          </ZanzibarGate>
        </div>
      </PermissionProvider>
    );
  },
};

/**
 * HiddenNoFallback: When gate denies and no fallback is provided,
 * nothing renders. This demonstrates the default behavior.
 */
export const HiddenNoFallback: Story = {
  decorators: [withPermissionProvider(RESTRICTED_AUTHZ)],
  render: () => (
    <div className="w-[480px]">
      <div className="mb-3">
        <span className="text-xs font-medium text-gray-400">
          relation: can_view | objectType: module | objectId: WAREHOUSE (no fallback)
        </span>
      </div>
      <div className="rounded border border-dashed border-gray-300 p-4 text-center text-xs text-gray-400">
        Asagida ZanzibarGate var ama erisim olmadigi ve fallback verilmedigi icin icerik gorunmuyor:
      </div>
      <ZanzibarGate relation="can_view" objectType="module" objectId="WAREHOUSE">
        <ProtectedDashboard />
      </ZanzibarGate>
      <div className="mt-2 rounded border border-dashed border-gray-300 p-4 text-center text-xs text-gray-400">
        Gate sonrasi alan — icerik gorunmuyor.
      </div>
    </div>
  ),
};

/**
 * Interactive Playground: Toggle between different auth states
 * to see ZanzibarGate behavior live.
 */
export const InteractivePlayground: Story = {
  render: () => {
    const [scenario, setScenario] = useState<'superadmin' | 'authorized' | 'denied'>('authorized');

    const authzMap: Record<string, AuthzMeResponse> = {
      superadmin: SUPER_ADMIN_AUTHZ,
      authorized: BASE_AUTHZ,
      denied: RESTRICTED_AUTHZ,
    };

    const currentAuthz = authzMap[scenario];

    return (
      <div className="w-[520px] space-y-4">
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-3">
          <div className="mb-2 text-xs font-medium text-gray-500">Scenario</div>
          <div className="flex gap-2">
            {(['superadmin', 'authorized', 'denied'] as const).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setScenario(s)}
                className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
                  scenario === s
                    ? 'bg-blue-600 text-white'
                    : 'border border-gray-300 bg-white text-gray-600 hover:bg-gray-100'
                }`}
              >
                {s === 'superadmin' ? 'SuperAdmin' : s === 'authorized' ? 'Yetkili' : 'Engelli'}
              </button>
            ))}
          </div>
          <div className="mt-2 text-xs text-gray-400">
            userId: {currentAuthz.userId} | superAdmin: {String(currentAuthz.superAdmin)} |
            roles: {currentAuthz.roles?.join(', ')}
          </div>
        </div>

        <PermissionProvider
          key={scenario}
          httpGet={mockHttpGet(currentAuthz)}
          initialData={currentAuthz}
        >
          <ZanzibarGate
            relation="can_view"
            objectType="module"
            objectId="AUDIT"
            fallback={
              <div className="rounded-lg border border-red-200 bg-red-50 p-4">
                <h3 className="text-sm font-semibold text-red-800">Erisim Engellendi</h3>
                <p className="mt-1 text-xs text-red-600">AUDIT modulune erisim yetkiniz yok.</p>
              </div>
            }
          >
            <ProtectedDashboard />
          </ZanzibarGate>
        </PermissionProvider>
      </div>
    );
  },
};
