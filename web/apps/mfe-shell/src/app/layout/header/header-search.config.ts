import { MODULE_KEYS } from '../../../features/auth/lib/permissions.constants';

/* ------------------------------------------------------------------ */
/*  Searchable items for GlobalSearch / CommandPalette                  */
/* ------------------------------------------------------------------ */

export interface SearchableItem {
  id: string;
  titleKey: string;
  descriptionKey?: string;
  group: 'navigation' | 'reports' | 'commands' | 'tools';
  path?: string;
  shortcut?: string;
  keywords: string[];
  permission?: string;
  remoteFlag?: 'suggestions' | 'ethic';
}

export const SEARCHABLE_ITEMS: SearchableItem[] = [
  // Navigation
  { id: 'nav-home', titleKey: 'shell.nav.home', group: 'navigation', path: '/', keywords: ['home', 'ana', 'sayfa', 'dashboard'] },
  { id: 'nav-suggestions', titleKey: 'shell.nav.suggestions', group: 'navigation', path: '/suggestions', keywords: ['suggestions', 'oneri', 'oneriler'], remoteFlag: 'suggestions' },
  { id: 'nav-ethic', titleKey: 'shell.nav.ethic', group: 'navigation', path: '/ethic', keywords: ['ethic', 'etik'], remoteFlag: 'ethic' },
  { id: 'nav-users', titleKey: 'shell.nav.users', group: 'navigation', path: '/admin/users', keywords: ['users', 'kullanici', 'kullanicilar'], permission: MODULE_KEYS.USER_MANAGEMENT },
  { id: 'nav-access', titleKey: 'shell.nav.access', group: 'navigation', path: '/access/roles', keywords: ['access', 'erisim', 'roller', 'roles'], permission: MODULE_KEYS.ACCESS },
  { id: 'nav-audit', titleKey: 'shell.nav.audit', group: 'navigation', path: '/audit/events', keywords: ['audit', 'denetim', 'olaylar'], permission: MODULE_KEYS.AUDIT },
  { id: 'nav-services', titleKey: 'shell.nav.services', group: 'navigation', path: '/admin/services', keywords: ['services', 'servisler', 'servis'], permission: MODULE_KEYS.THEME },

  // Reports
  { id: 'rpt-compensation', titleKey: 'shell.search.rpt.compensation', group: 'reports', path: '/admin/reports', keywords: ['compensation', 'ucret', 'maas', 'salary'], permission: MODULE_KEYS.REPORT },
  { id: 'rpt-demographic', titleKey: 'shell.search.rpt.demographic', group: 'reports', path: '/admin/reports', keywords: ['demographic', 'demografik', 'workforce'], permission: MODULE_KEYS.REPORT },
  { id: 'rpt-users', titleKey: 'shell.search.rpt.users', group: 'reports', path: '/admin/reports', keywords: ['users report', 'kullanici raporu'], permission: MODULE_KEYS.REPORT },
  { id: 'rpt-access', titleKey: 'shell.search.rpt.access', group: 'reports', path: '/admin/reports', keywords: ['access report', 'erisim raporu'], permission: MODULE_KEYS.REPORT },
  { id: 'rpt-audit', titleKey: 'shell.search.rpt.audit', group: 'reports', path: '/admin/reports', keywords: ['audit report', 'denetim raporu'], permission: MODULE_KEYS.REPORT },
  { id: 'rpt-monthly-login', titleKey: 'shell.search.rpt.monthlyLogin', group: 'reports', path: '/admin/reports', keywords: ['monthly login', 'aylik giris'], permission: MODULE_KEYS.REPORT },
  { id: 'rpt-weekly-audit', titleKey: 'shell.search.rpt.weeklyAudit', group: 'reports', path: '/admin/reports', keywords: ['weekly audit', 'haftalik denetim'], permission: MODULE_KEYS.REPORT },

  // Tools
  { id: 'tool-schema', titleKey: 'shell.search.tool.schema', group: 'tools', path: '/admin/schema-explorer', keywords: ['schema', 'explorer', 'database', 'veritabani', 'tablo'] },
  { id: 'tool-designlab', titleKey: 'shell.search.tool.designlab', group: 'tools', path: '/admin/design-lab', keywords: ['design lab', 'component', 'bilesen'], permission: MODULE_KEYS.THEME },
  { id: 'tool-themes', titleKey: 'shell.search.tool.themes', group: 'tools', path: '/admin/themes', keywords: ['theme', 'tema', 'gorunum'], permission: MODULE_KEYS.THEME },

  // Commands
  { id: 'cmd-theme-toggle', titleKey: 'shell.search.cmd.themeToggle', group: 'commands', keywords: ['theme', 'dark', 'light', 'tema', 'karanlik', 'acik'] },
  { id: 'cmd-lang-tr', titleKey: 'shell.search.cmd.langTr', group: 'commands', keywords: ['turkce', 'turkish', 'dil', 'language'] },
  { id: 'cmd-lang-en', titleKey: 'shell.search.cmd.langEn', group: 'commands', keywords: ['english', 'ingilizce', 'dil', 'language'] },
  { id: 'cmd-notifications', titleKey: 'shell.search.cmd.notifications', group: 'commands', shortcut: undefined, keywords: ['notifications', 'bildirimler', 'bildirim'] },
];

export const SEARCH_GROUP_LABELS: Record<string, string> = {
  recent: 'shell.search.group.recent',
  navigation: 'shell.search.group.navigation',
  reports: 'shell.search.group.reports',
  commands: 'shell.search.group.commands',
  tools: 'shell.search.group.tools',
  smartSuggestions: 'shell.search.group.smartSuggestions',
};
