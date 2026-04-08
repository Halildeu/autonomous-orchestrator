import type { LucideIcon } from 'lucide-react';
import {
  Users,
  Settings,
  Shield,
  FileSearch,
  Server,
  BarChart3,
  Database,
  Palette,
  Paintbrush,
  Wrench,
  PieChart,
  Lightbulb,
  Scale,
} from 'lucide-react';
import { PERMISSIONS, MODULE_KEYS } from '../../../features/auth/lib/permissions.constants';

/* ------------------------------------------------------------------ */
/*  Navigation types                                                   */
/* ------------------------------------------------------------------ */

export interface NavGroupItem {
  key: string;
  labelKey: string;
  descriptionKey?: string;
  path: string;
  icon: LucideIcon;
  /** @deprecated Use module instead. Legacy permission string for backward compat. */
  permission?: string;
  /** OpenFGA module key — preferred over permission. */
  module?: string;
  /** If true, item is only shown when the corresponding remote is enabled. */
  remoteFlag?: 'suggestions' | 'ethic';
}

export interface NavGroup {
  key: string;
  labelKey: string;
  icon: LucideIcon;
  /** @deprecated Use module instead. Legacy permission for the group itself. */
  permission?: string | 'any-child';
  /** OpenFGA module key — preferred over permission. */
  module?: string;
  /** Items inside a mega menu dropdown. Mutually exclusive with directPath. */
  items?: NavGroupItem[];
  /** Direct navigation path (no dropdown). Mutually exclusive with items. */
  directPath?: string;
}

export interface BreadcrumbRoute {
  pattern: string;
  labelKey: string;
  parent?: string;
  /** Sibling routes shown in breadcrumb dropdown for quick switching. */
  siblings?: string[];
}

/* ------------------------------------------------------------------ */
/*  Nav groups                                                         */
/* ------------------------------------------------------------------ */

export const NAV_GROUPS: NavGroup[] = [
  {
    key: 'hr',
    labelKey: 'shell.mega.hr',
    icon: Users,
    permission: 'any-child',
    items: [
      {
        key: 'suggestions',
        labelKey: 'shell.mega.hr.suggestions',
        descriptionKey: 'shell.mega.hr.suggestions.desc',
        path: '/suggestions',
        icon: Lightbulb,
        remoteFlag: 'suggestions',
      },
      {
        key: 'ethic',
        labelKey: 'shell.mega.hr.ethic',
        descriptionKey: 'shell.mega.hr.ethic.desc',
        path: '/ethic',
        icon: Scale,
        remoteFlag: 'ethic',
      },
      {
        key: 'compensation',
        labelKey: 'shell.mega.hr.compensation',
        descriptionKey: 'shell.mega.hr.compensation.desc',
        path: '/admin/reports',
        icon: BarChart3,
        module: MODULE_KEYS.REPORT,
        permission: PERMISSIONS.REPORTING_MODULE,
      },
      {
        key: 'demographic',
        labelKey: 'shell.mega.hr.demographic',
        descriptionKey: 'shell.mega.hr.demographic.desc',
        path: '/admin/reports',
        icon: PieChart,
        module: MODULE_KEYS.REPORT,
        permission: PERMISSIONS.REPORTING_MODULE,
      },
    ],
  },
  {
    key: 'admin',
    labelKey: 'shell.mega.admin',
    icon: Settings,
    permission: 'any-child',
    items: [
      {
        key: 'users',
        labelKey: 'shell.mega.admin.users',
        descriptionKey: 'shell.mega.admin.users.desc',
        path: '/admin/users',
        icon: Users,
        module: MODULE_KEYS.USER_MANAGEMENT,
        permission: PERMISSIONS.USER_MANAGEMENT_MODULE,
      },
      {
        key: 'access',
        labelKey: 'shell.mega.admin.access',
        descriptionKey: 'shell.mega.admin.access.desc',
        path: '/access/roles',
        icon: Shield,
        module: MODULE_KEYS.ACCESS,
        permission: PERMISSIONS.ACCESS_MODULE,
      },
      {
        key: 'audit',
        labelKey: 'shell.mega.admin.audit',
        descriptionKey: 'shell.mega.admin.audit.desc',
        path: '/audit/events',
        icon: FileSearch,
        module: MODULE_KEYS.AUDIT,
        permission: PERMISSIONS.AUDIT_MODULE,
      },
      {
        key: 'services',
        labelKey: 'shell.mega.admin.services',
        descriptionKey: 'shell.mega.admin.services.desc',
        path: '/admin/services',
        icon: Server,
        module: MODULE_KEYS.THEME,
        permission: PERMISSIONS.THEME_ADMIN,
      },
    ],
  },
  {
    key: 'reports',
    labelKey: 'shell.mega.reports',
    icon: BarChart3,
    directPath: '/admin/reports',
    module: MODULE_KEYS.REPORT,
    permission: PERMISSIONS.REPORTING_MODULE,
  },
  {
    key: 'tools',
    labelKey: 'shell.mega.tools',
    icon: Wrench,
    permission: 'any-child',
    items: [
      {
        key: 'schema',
        labelKey: 'shell.mega.tools.schema',
        descriptionKey: 'shell.mega.tools.schema.desc',
        path: '/admin/schema-explorer',
        icon: Database,
        module: MODULE_KEYS.THEME,
      },
      {
        key: 'designlab',
        labelKey: 'shell.mega.tools.designlab',
        descriptionKey: 'shell.mega.tools.designlab.desc',
        path: '/admin/design-lab',
        icon: Palette,
        module: MODULE_KEYS.THEME,
        permission: PERMISSIONS.THEME_ADMIN,
      },
      {
        key: 'themes',
        labelKey: 'shell.mega.tools.themes',
        descriptionKey: 'shell.mega.tools.themes.desc',
        path: '/admin/themes',
        icon: Paintbrush,
        module: MODULE_KEYS.THEME,
        permission: PERMISSIONS.THEME_ADMIN,
      },
    ],
  },
];

/* ------------------------------------------------------------------ */
/*  Breadcrumb route map                                               */
/* ------------------------------------------------------------------ */

export const BREADCRUMB_ROUTES: BreadcrumbRoute[] = [
  { pattern: '/', labelKey: 'shell.breadcrumb.home' },
  { pattern: '/home', labelKey: 'shell.breadcrumb.home', parent: '/' },

  // HR
  { pattern: '/suggestions', labelKey: 'shell.breadcrumb.suggestions', parent: '/' },
  { pattern: '/ethic', labelKey: 'shell.breadcrumb.ethic', parent: '/' },

  // Admin
  {
    pattern: '/admin/users',
    labelKey: 'shell.breadcrumb.users',
    parent: '/',
    siblings: ['/access/roles', '/audit/events', '/admin/services'],
  },
  {
    pattern: '/access/roles',
    labelKey: 'shell.breadcrumb.access',
    parent: '/',
    siblings: ['/admin/users', '/audit/events', '/admin/services'],
  },
  {
    pattern: '/audit/events',
    labelKey: 'shell.breadcrumb.audit',
    parent: '/',
    siblings: ['/admin/users', '/access/roles', '/admin/services'],
  },
  {
    pattern: '/admin/services',
    labelKey: 'shell.breadcrumb.services',
    parent: '/',
    siblings: ['/admin/users', '/access/roles', '/audit/events'],
  },

  // Reports
  {
    pattern: '/admin/reports',
    labelKey: 'shell.breadcrumb.reports',
    parent: '/',
  },
  {
    pattern: '/admin/reports/builder',
    labelKey: 'shell.breadcrumb.reportBuilder',
    parent: '/admin/reports',
  },
  {
    pattern: '/admin/reports/builder/dashboard',
    labelKey: 'shell.breadcrumb.dashboardBuilder',
    parent: '/admin/reports/builder',
  },

  // Tools
  {
    pattern: '/admin/schema-explorer',
    labelKey: 'shell.breadcrumb.schemaExplorer',
    parent: '/',
    siblings: ['/admin/design-lab', '/admin/themes'],
  },
  {
    pattern: '/admin/design-lab',
    labelKey: 'shell.breadcrumb.designLab',
    parent: '/',
    siblings: ['/admin/schema-explorer', '/admin/themes'],
  },
  {
    pattern: '/admin/themes',
    labelKey: 'shell.breadcrumb.themes',
    parent: '/',
    siblings: ['/admin/schema-explorer', '/admin/design-lab'],
  },
];
