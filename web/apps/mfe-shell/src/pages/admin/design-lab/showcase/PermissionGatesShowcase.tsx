import React, { useState } from 'react';
import { PermissionProvider, ZanzibarGate, useZanzibarAccess } from '@mfe/auth';
import type { AuthzMeResponse, ZanzibarAccessLevel } from '@mfe/auth';
import type { ComponentShowcaseSection } from './showcaseTypes';

/**
 * Design Lab showcase for Zanzibar-Aware Permission Gates.
 * CNS-20260411-005: 3 canonical scenarios + interactive playground.
 * Auth & Security UI > Permission Gates.
 */

// --- Mock data for showcase ---

const MOCK_SCENARIOS: Array<{
  label: string;
  description: string;
  relation: string;
  objectType: string;
  objectId: string;
  expectedAccess: ZanzibarAccessLevel;
  authzOverride: Partial<AuthzMeResponse>;
  httpPostResult: { allowed: boolean; reason: string };
}> = [
  {
    label: 'Full Access (can_manage)',
    description: 'User has MANAGE permission — full interaction allowed',
    relation: 'can_manage',
    objectType: 'module',
    objectId: 'AUDIT',
    expectedAccess: 'full',
    authzOverride: { superAdmin: true },
    httpPostResult: { allowed: true, reason: 'granted' },
  },
  {
    label: 'Read-Only (can_view)',
    description: 'User can view but not edit — opacity 70%, interaction blocked',
    relation: 'can_view',
    objectType: 'report',
    objectId: 'HR_REPORTS',
    expectedAccess: 'readonly',
    authzOverride: {
      superAdmin: false,
      modules: { REPORT: 'VIEW' },
      reports: { HR_REPORTS: 'ALLOW' },
    },
    httpPostResult: { allowed: true, reason: 'granted' },
  },
  {
    label: 'Disabled (blocked)',
    description: 'User is explicitly blocked — opacity 50%, cursor not-allowed',
    relation: 'can_edit',
    objectType: 'report',
    objectId: 'FINANCE_REPORTS',
    expectedAccess: 'disabled',
    authzOverride: {
      superAdmin: false,
      modules: { REPORT: 'VIEW' },
      reports: { FINANCE_REPORTS: 'ALLOW' },
    },
    httpPostResult: { allowed: false, reason: 'blocked' },
  },
  {
    label: 'Hidden (no_relation)',
    description: 'No relation exists — element is invisible',
    relation: 'can_view',
    objectType: 'report',
    objectId: 'SECRET_REPORTS',
    expectedAccess: 'hidden',
    authzOverride: {
      superAdmin: false,
      modules: {},
      reports: { SECRET_REPORTS: 'DENY' },
    },
    httpPostResult: { allowed: false, reason: 'no_relation' },
  },
];

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

// --- Internal components ---

function AccessLevelBadge({ level }: { level: ZanzibarAccessLevel }) {
  const styles: Record<ZanzibarAccessLevel, string> = {
    full: 'bg-green-100 text-green-800 border-green-300',
    readonly: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    disabled: 'bg-red-100 text-red-800 border-red-300',
    hidden: 'bg-gray-100 text-gray-500 border-gray-300',
  };
  return (
    <span className={`inline-block px-2 py-0.5 text-xs font-medium rounded border ${styles[level]}`}>
      {level}
    </span>
  );
}

function ScenarioCard({ scenario }: { scenario: typeof MOCK_SCENARIOS[number] }) {
  const authz = { ...BASE_AUTHZ, ...scenario.authzOverride };
  const mockHttpGet = async () => ({ data: authz });
  const mockHttpPost = async () => ({ data: scenario.httpPostResult });

  return (
    <PermissionProvider httpGet={mockHttpGet} initialData={authz}>
      <div className="border rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="font-medium text-sm">{scenario.label}</h4>
          <AccessLevelBadge level={scenario.expectedAccess} />
        </div>
        <p className="text-xs text-gray-500">{scenario.description}</p>

        <div className="border-t pt-3 space-y-2">
          <div className="text-xs font-mono text-gray-400">
            relation: {scenario.relation} | objectType: {scenario.objectType} | objectId: {scenario.objectId}
          </div>

          <ZanzibarGate
            relation={scenario.relation}
            objectType={scenario.objectType}
            objectId={scenario.objectId}
            httpPost={mockHttpPost}
            fallback={
              <div className="p-3 bg-gray-50 rounded text-sm text-gray-400 italic">
                This content is hidden (no access)
              </div>
            }
            loadingFallback={
              <div className="p-3 bg-blue-50 rounded text-sm text-blue-400">
                Checking permissions...
              </div>
            }
          >
            <div className="p-3 bg-white border rounded text-sm">
              Protected content is visible
            </div>
          </ZanzibarGate>
        </div>
      </div>
    </PermissionProvider>
  );
}

function HookLiveDemo() {
  const [relation, setRelation] = useState('can_view');
  const [objectType, setObjectType] = useState('report');
  const [objectId, setObjectId] = useState('HR_REPORTS');
  const mockHttpPost = async () => ({
    data: { allowed: true, reason: 'granted' },
  });

  const { access, loading, reason } = useZanzibarAccess(
    relation, objectType, objectId, mockHttpPost
  );

  return (
    <div className="border rounded-lg p-4 space-y-3">
      <h4 className="font-medium text-sm">useZanzibarAccess Live</h4>

      <div className="grid grid-cols-3 gap-2">
        <div>
          <label className="text-xs text-gray-500">relation</label>
          <select
            value={relation}
            onChange={(e) => setRelation(e.target.value)}
            className="w-full text-xs border rounded p-1"
          >
            <option value="can_view">can_view</option>
            <option value="can_edit">can_edit</option>
            <option value="can_manage">can_manage</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500">objectType</label>
          <select
            value={objectType}
            onChange={(e) => setObjectType(e.target.value)}
            className="w-full text-xs border rounded p-1"
          >
            <option value="report">report</option>
            <option value="module">module</option>
            <option value="action">action</option>
            <option value="company">company</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500">objectId</label>
          <input
            value={objectId}
            onChange={(e) => setObjectId(e.target.value)}
            className="w-full text-xs border rounded p-1"
          />
        </div>
      </div>

      <div className="bg-gray-50 rounded p-3 font-mono text-xs space-y-1">
        <div>access: <AccessLevelBadge level={access} /></div>
        <div>loading: {String(loading)}</div>
        <div>reason: {reason}</div>
      </div>
    </div>
  );
}

function AccessLevelMatrix() {
  const levels: ZanzibarAccessLevel[] = ['full', 'readonly', 'disabled', 'hidden'];
  const descriptions: Record<ZanzibarAccessLevel, string> = {
    full: 'Full interaction — can_manage or can_edit granted',
    readonly: 'View only — opacity 70%, no interaction',
    disabled: 'Blocked — opacity 50%, cursor not-allowed',
    hidden: 'Invisible — no relation or explicitly denied',
  };
  const cssEffects: Record<ZanzibarAccessLevel, string> = {
    full: '',
    readonly: 'opacity-70 cursor-default',
    disabled: 'opacity-50 cursor-not-allowed pointer-events-none',
    hidden: 'invisible',
  };

  return (
    <div className="border rounded-lg p-4 space-y-3">
      <h4 className="font-medium text-sm">AccessLevel Matrix</h4>
      <div className="grid grid-cols-4 gap-3">
        {levels.map((level) => (
          <div key={level} className="space-y-2">
            <AccessLevelBadge level={level} />
            <div className={`p-3 border rounded text-sm ${cssEffects[level]}`}>
              <button className="px-3 py-1 bg-blue-500 text-white rounded text-xs">
                Edit Report
              </button>
            </div>
            <p className="text-xs text-gray-400">{descriptions[level]}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

// --- Main export ---

export function buildPermissionGatesSections(): ComponentShowcaseSection[] {
  return [
    {
      id: 'zanzibar-scenarios',
      eyebrow: 'Auth & Security UI',
      title: '4 Canonical Scenarios',
      description: 'ZanzibarGate + useZanzibarAccess with different access levels',
      badges: ['CNS-20260411-005', 'Faz 1.5'],
      content: (
        <div className="grid grid-cols-2 gap-4">
          {MOCK_SCENARIOS.map((s) => (
            <ScenarioCard key={s.label} scenario={s} />
          ))}
        </div>
      ),
    },
    {
      id: 'zanzibar-live-hook',
      title: 'useZanzibarAccess — Live Demo',
      description: 'Change relation/objectType/objectId and see access level in real-time',
      badges: ['Interactive'],
      content: <HookLiveDemo />,
    },
    {
      id: 'zanzibar-access-matrix',
      title: 'AccessLevel Matrix',
      description: 'Visual comparison of all 4 access states',
      badges: ['Reference'],
      content: <AccessLevelMatrix />,
    },
  ];
}
