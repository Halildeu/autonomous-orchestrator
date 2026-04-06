import React from 'react';
import {
  Activity,
  BarChart3,
  Bell,
  BookOpen,
  Bot,
  ClipboardList,
  FileText,
  Gauge,
  Globe2,
  Settings,
  Languages,
  LayoutDashboard,
  Package,
  Palette,
  Rocket,
  Search,
  Settings2,
  Shield,
  Sparkles,
  Users,
  Workflow,
} from 'lucide-react';
import {
  Badge,
  MenuBar,
  Text,
  createMenuBarItemsFromRoutes,
  type MenuBarItem,
  type MenuBarMenuItem,
  type MenuBarRouteInput,
} from '@mfe/design-system';
import {
  getMenuBarVariantDescriptor,
  normalizeMenuBarVariantId,
  type MenuBarVariantId,
} from '../../../../../../../../../packages/design-system/src/catalog/menu-bar-variant-catalog';

const iconClassName = 'h-4 w-4';

type InteractiveMenuBarRecipeConfig = {
  items?: MenuBarItem[];
  routes?: MenuBarRouteInput[];
  initialPath?: string;
  initialValue?: string;
  currentBadge?: React.ReactNode;
  startSlot?: React.ReactNode;
  endSlot?: React.ReactNode;
  contextTitle?: React.ReactNode;
  contextDescription?: React.ReactNode;
  contextMetrics?: Array<{
    label: React.ReactNode;
    value: React.ReactNode;
    tone?: React.ComponentProps<typeof Badge>['tone'];
  }>;
  supportingPanel?: React.ReactNode;
  access?: React.ComponentProps<typeof MenuBar>['access'];
  appearance?: React.ComponentProps<typeof MenuBar>['appearance'];
  size?: React.ComponentProps<typeof MenuBar>['size'];
  labelVisibility?: React.ComponentProps<typeof MenuBar>['labelVisibility'];
  overflowBehavior?: React.ComponentProps<typeof MenuBar>['overflowBehavior'];
  overflowLabel?: React.ComponentProps<typeof MenuBar>['overflowLabel'];
  maxVisibleItems?: React.ComponentProps<typeof MenuBar>['maxVisibleItems'];
  defaultFavoriteValues?: React.ComponentProps<typeof MenuBar>['defaultFavoriteValues'];
  showFavoriteToggle?: React.ComponentProps<typeof MenuBar>['showFavoriteToggle'];
  defaultRecentValues?: React.ComponentProps<typeof MenuBar>['defaultRecentValues'];
  recentLimit?: React.ComponentProps<typeof MenuBar>['recentLimit'];
  enableSearchHandoff?: React.ComponentProps<typeof MenuBar>['enableSearchHandoff'];
  searchPlaceholder?: React.ComponentProps<typeof MenuBar>['searchPlaceholder'];
  searchEmptyStateLabel?: React.ComponentProps<typeof MenuBar>['searchEmptyStateLabel'];
  submenuTrigger?: React.ComponentProps<typeof MenuBar>['submenuTrigger'];
  labelCollapseBreakpoint?: React.ComponentProps<typeof MenuBar>['labelCollapseBreakpoint'];
  responsiveBreakpoint?: React.ComponentProps<typeof MenuBar>['responsiveBreakpoint'];
  mobileFallback?: React.ComponentProps<typeof MenuBar>['mobileFallback'];
  utilityCollapse?: React.ComponentProps<typeof MenuBar>['utilityCollapse'];
  frameClassName?: string;
  surfaceClassName?: string;
  wrapperClassName?: string;
};

export type DesignLabMenuBarPreviewProps = {
  variantId: MenuBarVariantId;
  ariaLabel?: string;
  locale?: string;
};

type DesignLabMenuBarScenarioFrameProps = {
  variantId: MenuBarVariantId;
  children: React.ReactNode;
};

const getNodeText = (node: React.ReactNode): string => {
  if (typeof node === 'string' || typeof node === 'number') {
    return String(node);
  }
  if (Array.isArray(node)) {
    return node.map(getNodeText).join(' ');
  }
  if (React.isValidElement(node)) {
    return getNodeText((node.props as { children?: React.ReactNode }).children);
  }
  return '';
};

const resolveHrefForValue = (
  value: string,
  items: MenuBarItem[],
  routes: MenuBarRouteInput[],
) => {
  const directItem = items.find((item) => item.value === value);
  if (directItem?.href) {
    return directItem.href;
  }
  return routes.find((route) => route.value === value)?.href ?? '';
};

const DesignLabMenuBarMetaBlock: React.FC<{
  label: string;
  children: React.ReactNode;
}> = ({ label, children }) => (
  <div className="rounded-2xl border border-border-subtle bg-surface-panel p-4">
    <Text as="div" className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">
      {label}
    </Text>
    <div className="mt-3">{children}</div>
  </div>
);

const MenuBarSlotCluster: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="flex items-center gap-2">{children}</div>
);

const MenuBarIconChip: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <span className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-border-subtle bg-surface-default text-text-secondary">
    {children}
  </span>
);

const MenuBarMetricChip: React.FC<{
  label: React.ReactNode;
  value: React.ReactNode;
  tone?: React.ComponentProps<typeof Badge>['tone'];
}> = ({ label, value, tone = 'muted' }) => (
  <div className="rounded-2xl border border-border-subtle/70 bg-[var(--surface-card))] px-3 py-2 shadow-[0_14px_28px_-24px_var(--shadow-color))] ring-1 ring-[var(--border-subtle)]/20 backdrop-blur-xs">
    <Text as="div" className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">
      {label as string}
    </Text>
    <div className="mt-2 flex items-center gap-2">
      <span
        className={[
          'inline-flex h-2.5 w-2.5 rounded-full',
          tone === 'danger'
            ? 'bg-state-danger-text'
            : tone === 'warning'
              ? 'bg-state-warning-text'
              : tone === 'success'
                ? 'bg-state-success-text'
                : tone === 'info'
                  ? 'bg-state-info-text'
                  : 'bg-[var(--text-subtle)]',
        ].join(' ')}
      />
      <Text as="div" preset="body-sm" className="text-sm font-semibold text-text-primary">
        {value as string}
      </Text>
    </div>
  </div>
);

export const DesignLabMenuBarScenarioFrame: React.FC<DesignLabMenuBarScenarioFrameProps> = ({
  variantId,
  children,
}) => {
  const variant = getMenuBarVariantDescriptor(variantId);

  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-[24px] border border-border-subtle bg-surface-panel p-5 shadow-xs">
        {children}
      </div>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <DesignLabMenuBarMetaBlock label="Modes">
          <div className="flex flex-wrap gap-2">
            {variant.modes.map((mode) => (
              <span
                key={mode}
                className="inline-flex items-center rounded-full border border-border-subtle bg-surface-default px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-text-secondary"
              >
                {mode}
              </span>
            ))}
          </div>
        </DesignLabMenuBarMetaBlock>
        <DesignLabMenuBarMetaBlock label="Pattern badges">
          <div className="flex flex-wrap gap-2">
            {variant.badges.map((badge) => (
              <span
                key={badge}
                className="inline-flex items-center rounded-full border border-border-subtle bg-surface-default px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-text-secondary"
              >
                {badge}
              </span>
            ))}
          </div>
        </DesignLabMenuBarMetaBlock>
        <DesignLabMenuBarMetaBlock label="Variant axes">
          <div className="flex flex-wrap gap-2">
            {variant.variantAxes.map((axis) => (
              <span
                key={axis}
                className="inline-flex items-center rounded-full border border-border-subtle bg-surface-default px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-text-secondary"
              >
                {axis}
              </span>
            ))}
          </div>
        </DesignLabMenuBarMetaBlock>
        <DesignLabMenuBarMetaBlock label="State model">
          <div className="flex flex-wrap gap-2">
            {variant.stateModel.map((state) => (
              <span
                key={state}
                className="inline-flex items-center rounded-full border border-border-subtle bg-surface-default px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-text-secondary"
              >
                {state}
              </span>
            ))}
          </div>
        </DesignLabMenuBarMetaBlock>
        <DesignLabMenuBarMetaBlock label="Primary benchmark">
          <div className="flex flex-wrap gap-2">
            {variant.benchmarkPrimary.map((source) => (
              <span
                key={source}
                className="inline-flex items-center rounded-full border border-border-subtle bg-surface-default px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-text-secondary"
              >
                {source}
              </span>
            ))}
          </div>
        </DesignLabMenuBarMetaBlock>
        <DesignLabMenuBarMetaBlock label="Secondary reference">
          <div className="flex flex-wrap gap-2">
            {variant.benchmarkSecondary.map((source) => (
              <span
                key={source}
                className="inline-flex items-center rounded-full border border-border-subtle bg-surface-default px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-text-secondary"
              >
                {source}
              </span>
            ))}
          </div>
        </DesignLabMenuBarMetaBlock>
        <DesignLabMenuBarMetaBlock label="Preview focus">
          <Text preset="body" className="leading-7 text-text-primary">
            {variant.previewFocus.join(' | ')}
          </Text>
        </DesignLabMenuBarMetaBlock>
        <DesignLabMenuBarMetaBlock label="Regression focus">
          <Text preset="body" className="leading-7 text-text-primary">
            {variant.regressionFocus.join(' | ')}
          </Text>
        </DesignLabMenuBarMetaBlock>
      </div>
    </div>
  );
};

const buildInteractiveVariantConfig = (
  variantId: MenuBarVariantId,
  locale: string,
): InteractiveMenuBarRecipeConfig => {
  const isTurkish = locale.startsWith('tr');
  const t = (tr: string, en: string) => (isTurkish ? tr : en);
  const resolvedVariantId = normalizeMenuBarVariantId(variantId);

  switch (resolvedVariantId) {
    case 'app_header':
      return {
        routes: [
          { value: 'overview', label: t('Genel Bakış', 'Overview'), href: '/app/overview', icon: <LayoutDashboard className={iconClassName} />, overflowPriority: 8, group: 'primary' },
          { value: 'approval', label: t('Onaylar', 'Approvals'), href: '/app/approval', icon: <Shield className={iconClassName} />, overflowPriority: 10, pinned: true, group: 'primary', emphasis: 'promoted' },
          {
            value: 'inbox',
            label: 'Inbox',
            href: '/app/inbox',
            icon: <Bell className={iconClassName} />,
            overflowPriority: 9,
            badge: '12',
            group: 'primary',
            menuItems: [
              { key: 'high', label: t('Yüksek sinyal', 'High signal'), groupLabel: t('Priority', 'Priority'), badge: '3', danger: true },
              { key: 'all', label: t('Tüm inbox', 'All inbox'), groupLabel: t('Priority', 'Priority') },
            ],
          },
          { value: 'reports', label: t('Raporlar', 'Reports'), href: '/app/reports', icon: <BarChart3 className={iconClassName} />, overflowPriority: 7, group: 'secondary' },
          { value: 'docs', label: 'Docs', href: '/app/docs', icon: <FileText className={iconClassName} />, overflowPriority: 4, group: 'utility', emphasis: 'subtle' },
        ],
        appearance: 'outline',
        size: 'sm',
        labelVisibility: 'responsive',
        labelCollapseBreakpoint: '(max-width: 1200px)',
        overflowBehavior: 'collapse-to-more',
        overflowLabel: t('Menü', 'Menu'),
        maxVisibleItems: 4,
        responsiveBreakpoint: '(max-width: 960px)',
        mobileFallback: 'menu',
        utilityCollapse: 'hide',
        initialPath: '/app/approval',
        startSlot: <Badge variant="muted">{t('Platform', 'Platform')}</Badge>,
        endSlot: (
          <MenuBarSlotCluster>
            <Badge variant="info">Admin</Badge>
            <MenuBarIconChip>
              <Bell className={iconClassName} />
            </MenuBarIconChip>
            <Badge variant="muted">HK</Badge>
          </MenuBarSlotCluster>
        ),
        contextTitle: t('Canonical app header', 'Canonical app header'),
        contextDescription: t(
          'Branding, route navigation ve utility cluster ayni ust bar icinde sakin kalir. Dar gorunumde menu fallback ile basligi dagitmaz.',
          'Branding, route navigation, and the utility cluster stay calm in the same top bar. On narrow viewports it falls back to Menu instead of fragmenting the header.',
        ),
        contextMetrics: [
          { label: t('Responsive', 'Responsive'), value: '960px', tone: 'info' },
          { label: t('Inbox', 'Inbox'), value: '12', tone: 'warning' },
          { label: t('Role', 'Role'), value: 'Admin', tone: 'success' },
        ],
      };
    case 'navigation_menu':
      return {
        routes: [
          { value: 'packages', label: t('Packages', 'Packages'), href: '/library/packages', icon: <Package className={iconClassName} />, overflowPriority: 10, group: 'primary', emphasis: 'promoted' },
          {
            value: 'tokens',
            label: t('Tokens', 'Tokens'),
            href: '/library/tokens',
            icon: <Palette className={iconClassName} />,
            overflowPriority: 9,
            group: 'primary',
            menuSurfaceTitle: t('Token catalog', 'Token catalog'),
            menuSurfaceDescription: t(
              'Navigasyon sadece link listesi degil; konuya giris yapan aciklayici bir submenu paneli gibi davranir.',
              'Navigation acts not only as a link list but as an explanatory submenu panel that introduces the area.',
            ),
            menuSurfaceMeta: (
              <div className="flex flex-wrap gap-2">
                <Badge variant="info">{t('Visual', 'Visual')}</Badge>
                <Badge variant="success">{t('Layout', 'Layout')}</Badge>
              </div>
            ),
            menuItems: [
              { key: 'theme', label: t('Theme tokens', 'Theme tokens'), groupLabel: t('Visual', 'Visual'), description: t('Renk, surface ve highlight', 'Color, surface, and highlight') },
              { key: 'motion', label: t('Motion tokens', 'Motion tokens'), groupLabel: t('Visual', 'Visual'), description: t('Entrance ve micro-motion', 'Entrance and micro-motion') },
              { key: 'density', label: t('Density tokens', 'Density tokens'), groupLabel: t('Layout', 'Layout'), description: t('Compact ve comfortable ritimler', 'Compact and comfortable rhythms') },
            ],
          },
          { value: 'recipes', label: t('Recipe’ler', 'Recipes'), href: '/library/recipes', icon: <BookOpen className={iconClassName} />, overflowPriority: 8, group: 'secondary' },
          { value: 'patterns', label: t('Pattern’ler', 'Patterns'), href: '/library/patterns', icon: <Sparkles className={iconClassName} />, overflowPriority: 7, group: 'secondary' },
          { value: 'docs', label: 'Docs', href: '/library/docs', icon: <FileText className={iconClassName} />, overflowPriority: 4, group: 'utility', emphasis: 'subtle' },
        ],
        appearance: 'default',
        size: 'md',
        labelVisibility: 'responsive',
        labelCollapseBreakpoint: '(max-width: 1200px)',
        overflowBehavior: 'collapse-to-more',
        overflowLabel: t('Daha fazla', 'More'),
        maxVisibleItems: 4,
        initialPath: '/library/packages',
        currentBadge: <Badge variant="info">{t('Current', 'Current')}</Badge>,
        startSlot: <Badge variant="muted">{t('Library', 'Library')}</Badge>,
        endSlot: <Badge variant="success">v3.4</Badge>,
        contextTitle: t('Canonical navigation menu', 'Canonical navigation menu'),
        contextDescription: t(
          'Bilgi kokusu yuksek, route gruplari okunur ve submenu paneli aciklayicidir. Buyuk IA icin menu bar’dan navigation menu hissine gecis verir.',
          'High information scent, readable route groups, and an explanatory submenu panel. It shifts the menubar toward a true navigation menu for large IA.',
        ),
        contextMetrics: [
          { label: t('Brand', 'Brand'), value: 'Library', tone: 'info' },
          { label: t('Routes', 'Routes'), value: '5', tone: 'success' },
          { label: t('Panel', 'Panel'), value: t('Rich', 'Rich'), tone: 'warning' },
        ],
      };
    case 'search_command_header':
      return {
        routes: [
          { value: 'overview', label: t('Genel Bakış', 'Overview'), href: '/console/overview', icon: <LayoutDashboard className={iconClassName} />, overflowPriority: 8, group: 'primary', keywords: ['dashboard', 'summary'] },
          {
            value: 'approval',
            label: t('Onaylar', 'Approvals'),
            href: '/console/approval',
            icon: <Shield className={iconClassName} />,
            overflowPriority: 10,
            pinned: true,
            group: 'primary',
            emphasis: 'promoted',
            keywords: ['approve', 'review', 'governance', 'queue'],
            menuSurfaceTitle: t('Approval cockpit', 'Approval cockpit'),
            menuSurfaceDescription: t(
              'Root ile alt komutlar ayni arama ve panel deneyimine baglanir; search handoff rota ve komut arasindaki surtünmeyi azaltir.',
              'The root and nested commands connect to the same search and panel experience; search handoff reduces friction between route and command.',
            ),
            menuSurfaceMeta: (
              <div className="flex flex-wrap gap-2">
                <Badge variant="warning">{t('4 sıcak öğe', '4 hot items')}</Badge>
                <Badge variant="info">⌘K</Badge>
              </div>
            ),
            menuItems: [
              { key: 'pending', label: t('Bekleyen onaylar', 'Pending approvals'), groupLabel: t('Review', 'Review'), description: t('Sıcak kuyruk', 'Hot queue') },
              { key: 'history', label: t('Karar geçmişi', 'Decision history'), groupLabel: t('Review', 'Review'), description: t('Son kararlar', 'Recent decisions') },
              { key: 'handoff', label: t('Owner handoff', 'Owner handoff'), groupLabel: t('Operations', 'Operations'), description: t('Sahiplik devri', 'Owner transfer') },
            ],
          },
          {
            value: 'lanes',
            label: t('Lane’ler', 'Lanes'),
            href: '/console/lanes',
            icon: <Workflow className={iconClassName} />,
            overflowPriority: 9,
            group: 'secondary',
            keywords: ['resume', 'pause', 'budget', 'delivery'],
            menuItems: [
              { key: 'resume', label: t('Lane devam ettir', 'Resume lane'), groupLabel: t('Delivery', 'Delivery'), shortcut: '⌘R' },
              { key: 'pause', label: t('Lane duraklat', 'Pause lane'), groupLabel: t('Delivery', 'Delivery'), shortcut: '⌘P' },
            ],
          },
          { value: 'insights', label: t('İçgörü', 'Insights'), href: '/console/insights', icon: <BarChart3 className={iconClassName} />, overflowPriority: 6, group: 'utility', emphasis: 'subtle', keywords: ['analytics', 'signals'] },
        ],
        appearance: 'outline',
        size: 'sm',
        labelVisibility: 'responsive',
        labelCollapseBreakpoint: '(max-width: 1200px)',
        overflowBehavior: 'collapse-to-more',
        overflowLabel: t('Araçlar', 'Tools'),
        maxVisibleItems: 4,
        showFavoriteToggle: true,
        defaultFavoriteValues: ['approval', 'lanes'],
        defaultRecentValues: ['approval', 'lanes', 'overview'],
        recentLimit: 6,
        enableSearchHandoff: true,
        searchPlaceholder: t('Rota veya komut ara', 'Search routes or commands'),
        searchEmptyStateLabel: t('Eşleşen rota veya komut bulunamadı.', 'No matching routes or commands.'),
        initialPath: '/console/approval',
        startSlot: (
          <div className="flex items-center gap-2 rounded-full border border-border-subtle/70 bg-[var(--surface-card))] px-3 py-1.5 shadow-[0_12px_24px_-24px_var(--shadow-color))] ring-1 ring-[var(--border-subtle)]/20 backdrop-blur-xs">
            <Search className={iconClassName} />
            <Text variant="secondary" className="text-xs">{t('Ara, komut çalıştır, rota aç', 'Search, run a command, open a route')}</Text>
            <Badge variant="muted">⌘K</Badge>
          </div>
        ),
        endSlot: (
          <MenuBarSlotCluster>
            <Badge variant="info">{t('Search', 'Search')}</Badge>
            <Badge variant="success">{t('Canlı', 'Live')}</Badge>
          </MenuBarSlotCluster>
        ),
        contextTitle: t('Canonical search / command header', 'Canonical search / command header'),
        contextDescription: t(
          'Search handoff, favorites ve recent roots ayni ust kabukta toplandiginda modern urun hissi belirginlesir.',
          'When search handoff, favorites, and recent roots are gathered in the same top shell, the modern product feel becomes much stronger.',
        ),
        contextMetrics: [
          { label: t('Shortcut', 'Shortcut'), value: '⌘K', tone: 'info' },
          { label: t('Favorites', 'Favorites'), value: '2', tone: 'warning' },
          { label: t('Recent', 'Recent'), value: '3', tone: 'success' },
        ],
      };
    case 'action_header':
      return {
        items: [
          { value: 'assign', label: t('Ata', 'Assign'), icon: <Users className={iconClassName} />, group: 'primary', emphasis: 'promoted' },
          { value: 'tag', label: t('Etiketle', 'Tag'), icon: <Palette className={iconClassName} />, group: 'primary' },
          {
            value: 'policy',
            label: t('Policy', 'Policy'),
            icon: <Shield className={iconClassName} />,
            group: 'secondary',
            menuSurfaceTitle: t('Governance actions', 'Governance actions'),
            menuSurfaceDescription: t(
              'Toplu secim akisini bozmadan review ve archive kararlarini tek panelde toplar.',
              'Collects review and archive decisions in one panel without breaking the bulk-selection flow.',
            ),
            menuItems: [
              { key: 'approve', label: t('Onaya gönder', 'Send for approval'), groupLabel: t('Governance', 'Governance') },
              { key: 'archive', label: t('Arşive taşı', 'Move to archive'), groupLabel: t('Governance', 'Governance') },
            ],
          },
          { value: 'export', label: t('Dışa Aktar', 'Export'), icon: <FileText className={iconClassName} />, group: 'utility', emphasis: 'subtle' },
        ],
        appearance: 'outline',
        size: 'sm',
        labelVisibility: 'responsive',
        labelCollapseBreakpoint: '(max-width: 1200px)',
        initialValue: 'assign',
        startSlot: <Badge variant="warning">{t('24 seçim', '24 selected')}</Badge>,
        endSlot: (
          <MenuBarSlotCluster>
            <Badge variant="info">{t('Toplu işlem', 'Bulk action')}</Badge>
            <Badge variant="muted">{t('Review mode', 'Review mode')}</Badge>
          </MenuBarSlotCluster>
        ),
        contextTitle: t('Canonical action header', 'Canonical action header'),
        contextDescription: t(
          'Selection context ayni bardan gorulur ve kullanici bulk aksiyonlar icin sayfa icine dagilmaz.',
          'The selection context is visible in the same bar, so users do not have to chase bulk actions across the page.',
        ),
        contextMetrics: [
          { label: t('Selection', 'Selection'), value: '24', tone: 'warning' },
          { label: t('Actions', 'Actions'), value: '4', tone: 'info' },
          { label: t('Mode', 'Mode'), value: t('Review', 'Review'), tone: 'success' },
        ],
      };
    case 'desktop_menubar':
      return {
        items: [
          {
            value: 'file',
            label: t('Dosya', 'File'),
            icon: <FileText className={iconClassName} />,
            menuItems: [
              { key: 'new', label: t('Yeni pencere', 'New window'), groupLabel: t('File', 'File') },
              { key: 'open', label: t('Son kullanılanı aç', 'Open recent'), groupLabel: t('File', 'File') },
            ],
          },
          {
            value: 'view',
            label: t('Görünüm', 'View'),
            icon: <LayoutDashboard className={iconClassName} />,
            menuItems: [
              { key: 'comfortable', label: t('Comfortable', 'Comfortable'), type: 'radio', checked: true, groupLabel: t('Density', 'Density') },
              { key: 'compact', label: t('Compact', 'Compact'), type: 'radio', groupLabel: t('Density', 'Density') },
              { key: 'grid-lines', label: t('Grid çizgileri', 'Grid lines'), type: 'checkbox', checked: true, groupLabel: t('Display', 'Display') },
            ],
          },
          {
            value: 'tools',
            label: t('Araçlar', 'Tools'),
            icon: <Settings2 className={iconClassName} />,
            menuItems: [
              { key: 'preferences', label: t('Tercihler', 'Preferences'), groupLabel: t('Tools', 'Tools') },
              { key: 'extensions', label: t('Eklentiler', 'Extensions'), groupLabel: t('Tools', 'Tools') },
            ],
          },
          {
            value: 'help',
            label: t('Yardım', 'Help'),
            icon: <Settings className={iconClassName} />,
            href: '/desktop/help',
          },
        ],
        appearance: 'outline',
        size: 'sm',
        labelVisibility: 'responsive',
        labelCollapseBreakpoint: '(max-width: 1200px)',
        submenuTrigger: 'hover',
        initialValue: 'file',
        startSlot: <Badge variant="muted">{t('Desktop mode', 'Desktop mode')}</Badge>,
        endSlot: <Badge variant="info">{t('Local app', 'Local app')}</Badge>,
        contextTitle: t('Canonical desktop menubar', 'Canonical desktop menubar'),
        contextDescription: t(
          'Gercek masaustu hissi icin file/view/tools yapisi ve typed submenu parity gerekir; hover/click duzeni bu tarifte gorunur.',
          'A real desktop feel needs the file/view/tools structure and typed submenu parity; the hover/click rhythm is visible in this recipe.',
        ),
        contextMetrics: [
          { label: t('Typed items', 'Typed items'), value: 'radio + checkbox', tone: 'info' },
          { label: t('Density', 'Density'), value: 'Comfortable', tone: 'success' },
          { label: t('Trigger', 'Trigger'), value: t('Hover', 'Hover'), tone: 'warning' },
        ],
      };
    case 'overflow_more':
      return {
        routes: [
          { value: 'overview', label: t('Overview', 'Overview'), href: '/release/overview', icon: <LayoutDashboard className={iconClassName} />, overflowPriority: 5 },
          { value: 'rollout', label: t('Rollout', 'Rollout'), href: '/release/rollout', icon: <Rocket className={iconClassName} />, overflowPriority: 8 },
          { value: 'approvals', label: t('Onaylar', 'Approvals'), href: '/release/approvals', icon: <Shield className={iconClassName} />, overflowPriority: 10 },
          { value: 'signals', label: t('Sinyaller', 'Signals'), href: '/release/signals', icon: <Bell className={iconClassName} />, overflowPriority: 7 },
          { value: 'audit', label: t('Audit', 'Audit'), href: '/release/audit', icon: <Activity className={iconClassName} />, overflowPriority: 6 },
          { value: 'docs', label: t('Docs', 'Docs'), href: '/release/docs', icon: <FileText className={iconClassName} />, overflowPriority: 2 },
        ],
        appearance: 'outline',
        size: 'sm',
        labelVisibility: 'always',
        overflowBehavior: 'collapse-to-more',
        overflowLabel: t('Daha fazla', 'More'),
        maxVisibleItems: 3,
        initialPath: '/release/approvals',
        currentBadge: <Badge variant="warning">{t('Odak', 'Focus')}</Badge>,
        endSlot: <Badge variant="danger">{t('İnsident 1', 'Incident 1')}</Badge>,
        contextTitle: t('Overflow kontrollü release bar', 'Overflow-controlled release bar'),
        contextDescription: t(
          'AntD benzeri More davranışını yalnız dar ekranda değil, büyük IA büyüdüğünde de bilinçli sadeleştirme için kullanır.',
          'Uses an AntD-style More pattern not only on narrow screens but as a deliberate simplification strategy when IA grows.',
        ),
        contextMetrics: [
          { label: t('Görünür root', 'Visible roots'), value: '3/6', tone: 'info' },
          { label: t('Overflow etiketi', 'Overflow label'), value: t('Daha fazla', 'More'), tone: 'muted' },
          { label: t('Kritik modül', 'Critical module'), value: t('Onaylar', 'Approvals'), tone: 'warning' },
        ],
        supportingPanel: (
          <div className="rounded-[22px] border border-border-subtle/70 bg-[var(--surface-card))] p-4 shadow-[0_20px_38px_-30px_var(--shadow-color))]">
            <div className="flex items-center justify-between gap-3">
              <div>
                <Text as="div" className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">
                  {t('Overflow kararı', 'Overflow decision')}
                </Text>
                <Text as="div" preset="body-sm" className="mt-1 text-sm font-semibold text-text-primary">
                  {t('Gizlenen rotalar bağlamı kaybetmiyor', 'Hidden routes do not lose context')}
                </Text>
              </div>
              <Badge variant="warning" className="rounded-full">
                priority
              </Badge>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-3">
              {[
                t('Signals More içine taşındı', 'Signals moved into More'),
                t('Docs düşük öncelik', 'Docs kept low priority'),
                t('Onaylar rootta sabit', 'Approvals retained on root'),
              ].map((entry) => (
                <div key={entry} className="rounded-2xl border border-border-subtle/70 bg-surface-default px-3 py-2">
                  <Text variant="secondary" className="text-xs leading-6">
                    {entry}
                  </Text>
                </div>
              ))}
            </div>
          </div>
        ),
        wrapperClassName: 'max-w-[480px] rounded-[26px] border border-border-subtle bg-surface-canvas p-3',
        frameClassName:
          'rounded-[28px] border border-state-warning-text/20/70 bg-[radial-gradient(circle_at_top_right,rgba(253,230,138,0.3),transparent_34%),linear-gradient(180deg,rgba(255,251,235,0.96),var(--surface-default)))] p-4 shadow-[0_34px_72px_-52px_var(--shadow-color))]',
        surfaceClassName:
          'rounded-[24px] border border-state-warning-text/20/70 bg-[var(--surface-card))] p-3 ring-1 ring-[var(--border-subtle)]/20 shadow-[0_22px_36px_-30px_rgba(217,119,6,0.24)]',
      };
    case 'responsive_app_header':
      return {
        routes: [
          { value: 'overview', label: t('Genel Bakış', 'Overview'), href: '/support/overview', icon: <LayoutDashboard className={iconClassName} />, overflowPriority: 6, group: 'primary' },
          { value: 'inbox', label: t('Inbox', 'Inbox'), href: '/support/inbox', icon: <Bell className={iconClassName} />, badge: '12', overflowPriority: 10, group: 'primary', emphasis: 'promoted' },
          {
            value: 'escalations',
            label: t('Escalations', 'Escalations'),
            href: '/support/escalations',
            icon: <Users className={iconClassName} />,
            overflowPriority: 9,
            group: 'primary',
            menuItems: [
              { key: 'sev1', label: 'Sev-1', groupLabel: t('Öncelik', 'Priority'), badge: '2', danger: true },
              { key: 'sev2', label: 'Sev-2', groupLabel: t('Öncelik', 'Priority'), badge: '5' },
              { key: 'handoff', label: t('Owner handoff', 'Owner handoff'), groupLabel: t('Operasyon', 'Operations') },
            ],
          },
          { value: 'sla', label: 'SLA', href: '/support/sla', icon: <Gauge className={iconClassName} />, overflowPriority: 8, group: 'secondary' },
          { value: 'exports', label: t('Dışa Aktarım', 'Exports'), href: '/support/exports', icon: <FileText className={iconClassName} />, overflowPriority: 3, group: 'utility', emphasis: 'subtle' },
        ],
        appearance: 'outline',
        size: 'sm',
        labelVisibility: 'responsive',
        labelCollapseBreakpoint: '(max-width: 1200px)',
        overflowBehavior: 'collapse-to-more',
        overflowLabel: t('Menü', 'Menu'),
        maxVisibleItems: 3,
        responsiveBreakpoint: '(max-width: 960px)',
        mobileFallback: 'menu',
        utilityCollapse: 'hide',
        initialPath: '/support/inbox',
        contextTitle: t('Responsive support header', 'Responsive support header'),
        contextDescription: t(
          'MUI AppBar çizgisinde; geniş ekranda route + utility, dar ekranda ise sakin menu fallback ile çalışan destek başlığı.',
          'A support header in the MUI AppBar spirit: route + utility on wide viewports and a calmer menu fallback on narrow ones.',
        ),
        contextMetrics: [
          { label: t('Breakpoint', 'Breakpoint'), value: '960px', tone: 'info' },
          { label: t('Inbox', 'Inbox'), value: '12', tone: 'warning' },
          { label: t('SLA riski', 'SLA risk'), value: '2h', tone: 'danger' },
        ],
        startSlot: <Badge variant="muted">{t('Support', 'Support')}</Badge>,
        endSlot: (
          <MenuBarSlotCluster>
            <Badge variant="warning">SLA 2h</Badge>
            <Badge variant="info">{t('Canlı', 'Live')}</Badge>
          </MenuBarSlotCluster>
        ),
        supportingPanel: (
          <div className="grid gap-3 md:grid-cols-2">
            {[
              {
                title: t('Mobil fallback', 'Mobile fallback'),
                body: t('Dar görünümde utility slot gizlenir ve ana yollar Menu altında toplanır.', 'On narrow viewports the utility slot hides and primary routes collapse under Menu.'),
              },
              {
                title: t('Operasyon kartı', 'Operations card'),
                body: t('Escalation ve SLA bağlamı üst çubukta kalır; agent görevleri sayfaya yayılmaz.', 'Escalation and SLA context stay in the header so agent tasks do not spill across the page.'),
              },
            ].map((card) => (
              <div key={card.title} className="rounded-[22px] border border-border-subtle/70 bg-[var(--surface-card))] p-4 shadow-[0_20px_38px_-30px_var(--shadow-color))]">
                <Text as="div" preset="body-sm" className="text-sm font-semibold text-text-primary">
                  {card.title}
                </Text>
                <Text variant="secondary" className="mt-1 text-xs leading-6">
                  {card.body}
                </Text>
              </div>
            ))}
          </div>
        ),
        wrapperClassName: 'max-w-[620px] rounded-[26px] border border-border-subtle bg-surface-canvas p-3',
        frameClassName:
          'rounded-[28px] border border-action-primary/20/70 bg-[radial-gradient(circle_at_top_left,rgba(221,214,254,0.34),transparent_34%),linear-gradient(180deg,rgba(248,250,255,0.98),rgba(243,244,255,0.94))] p-4 shadow-[0_34px_72px_-52px_rgba(91,33,182,0.22)]',
        surfaceClassName:
          'rounded-[24px] border border-action-primary/20/70 bg-[var(--surface-card))] p-3 ring-1 ring-[var(--border-subtle)]/20 shadow-[0_22px_36px_-30px_rgba(91,33,182,0.2)]',
      };
    case 'account_utility_cluster':
      return {
        routes: [
          { value: 'workspace', label: t('Workspace', 'Workspace'), href: '/product/workspace', icon: <LayoutDashboard className={iconClassName} />, overflowPriority: 7, group: 'primary' },
          { value: 'cases', label: t('Vaka', 'Cases'), href: '/product/cases', icon: <ClipboardList className={iconClassName} />, badge: '8', overflowPriority: 10, group: 'primary', emphasis: 'promoted' },
          { value: 'alerts', label: t('Alerts', 'Alerts'), href: '/product/alerts', icon: <Bell className={iconClassName} />, badge: '3', overflowPriority: 9, group: 'secondary' },
          { value: 'reports', label: t('Raporlar', 'Reports'), href: '/product/reports', icon: <BarChart3 className={iconClassName} />, overflowPriority: 6, group: 'secondary' },
          { value: 'docs', label: 'Docs', href: '/product/docs', icon: <BookOpen className={iconClassName} />, overflowPriority: 3, group: 'utility', emphasis: 'subtle' },
        ],
        appearance: 'default',
        size: 'md',
        labelVisibility: 'active',
        overflowBehavior: 'collapse-to-more',
        overflowLabel: t('Araçlar', 'Tools'),
        maxVisibleItems: 4,
        initialPath: '/product/cases',
        contextTitle: t('Product header + account cluster', 'Product header + account cluster'),
        contextDescription: t(
          'MUI Toolbar ve product shell yaklaşımına yakın; hesap, bildirim ve rol işlemlerini ayrı panel yerine üst çubukta tutar.',
          'Closer to MUI Toolbar and product shell patterns; keeps account, notifications, and role actions in the top bar instead of scattering them into separate panels.',
        ),
        contextMetrics: [
          { label: t('Açık vaka', 'Open cases'), value: '8', tone: 'warning' },
          { label: t('Yeni alarm', 'New alerts'), value: '3', tone: 'danger' },
          { label: t('Rol', 'Role'), value: 'Admin', tone: 'info' },
        ],
        startSlot: <Badge variant="success">{t('Product', 'Product')}</Badge>,
        endSlot: (
          <MenuBarSlotCluster>
            <Badge variant="info">Admin</Badge>
            <MenuBarIconChip>
              <Bell className={iconClassName} />
            </MenuBarIconChip>
            <Badge variant="muted">HK</Badge>
          </MenuBarSlotCluster>
        ),
        supportingPanel: (
          <div className="rounded-[22px] border border-border-subtle/70 bg-[var(--surface-card))] p-4 shadow-[0_20px_38px_-30px_var(--shadow-color))]">
            <div className="grid gap-3 md:grid-cols-3">
              {[
                { label: t('Bildirim merkezi', 'Notification center'), value: t('3 yüksek sinyal', '3 high signal') },
                { label: t('Hesap menüsü', 'Account menu'), value: t('Rol + şirket + çıkış', 'Role + company + sign out') },
                { label: t('Çalışma alanı', 'Workspace'), value: t('Cases odağı aktif', 'Cases focus active') },
              ].map((entry) => (
                <div key={entry.label} className="rounded-2xl border border-border-subtle/70 bg-surface-default px-3 py-2">
                  <Text as="div" className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">
                    {entry.label}
                  </Text>
                  <Text as="div" preset="body-sm" className="mt-1 text-sm font-semibold text-text-primary">
                    {entry.value}
                  </Text>
                </div>
              ))}
            </div>
          </div>
        ),
        frameClassName:
          'rounded-[28px] border border-state-success-text/20/70 bg-[radial-gradient(circle_at_top_right,rgba(187,247,208,0.34),transparent_34%),linear-gradient(180deg,rgba(247,254,250,0.98),var(--surface-default)))] p-4 shadow-[0_34px_72px_-52px_var(--shadow-color))]',
        surfaceClassName:
          'rounded-[24px] border border-state-success-text/20/70 bg-[var(--surface-card))] p-3 ring-1 ring-[var(--border-subtle)]/20 shadow-[0_22px_36px_-30px_rgba(5,150,105,0.18)]',
      };
    case 'pinned_favorites':
      return {
        routes: [
          { value: 'approval', label: t('Onaylar', 'Approvals'), href: '/enterprise/approval', icon: <Shield className={iconClassName} />, overflowPriority: 10, pinned: true, group: 'primary', emphasis: 'promoted', keywords: ['governance', 'review'], favoritable: true },
          { value: 'audit', label: t('Denetim', 'Audit'), href: '/enterprise/audit', icon: <Activity className={iconClassName} />, overflowPriority: 9, pinned: true, group: 'primary', keywords: ['events', 'evidence'], favoritable: true },
          { value: 'owners', label: t('Sahipler', 'Owners'), href: '/enterprise/owners', icon: <Users className={iconClassName} />, overflowPriority: 8, pinned: true, group: 'primary', keywords: ['handoff', 'directory'], favoritable: true },
          { value: 'analytics', label: t('Analitik', 'Analytics'), href: '/enterprise/analytics', icon: <BarChart3 className={iconClassName} />, overflowPriority: 7, group: 'secondary' },
          { value: 'exports', label: t('Dışa Aktarım', 'Exports'), href: '/enterprise/exports', icon: <FileText className={iconClassName} />, overflowPriority: 4, group: 'utility', emphasis: 'subtle' },
          { value: 'tokens', label: t('Tokens', 'Tokens'), href: '/enterprise/tokens', icon: <Palette className={iconClassName} />, overflowPriority: 3, group: 'utility', emphasis: 'subtle' },
        ],
        appearance: 'default',
        size: 'md',
        labelVisibility: 'always',
        overflowBehavior: 'collapse-to-more',
        overflowLabel: t('Favoriler dışı', 'More'),
        maxVisibleItems: 4,
        showFavoriteToggle: true,
        defaultFavoriteValues: ['approval', 'audit', 'owners'],
        defaultRecentValues: ['approval', 'owners'],
        initialPath: '/enterprise/approval',
        contextTitle: t('Pinned roots enterprise shell', 'Pinned roots enterprise shell'),
        contextDescription: t(
          'Büyük kurumsal bilgi mimarisinde kritik modülleri sabit tutar; geri kalan yollar kontrollü olarak overflow içine düşer.',
          'Keeps critical modules fixed in large enterprise information architectures while safely pushing the rest into controlled overflow.',
        ),
        contextMetrics: [
          { label: t('Pinned', 'Pinned'), value: '3', tone: 'warning' },
          { label: t('Toplam root', 'Total roots'), value: '6', tone: 'info' },
          { label: t('Overflow', 'Overflow'), value: t('Favoriler dışı', 'Non-favorites'), tone: 'muted' },
        ],
        startSlot: <Badge variant="warning">{t('Pinned', 'Pinned')}</Badge>,
        endSlot: <Badge variant="info">{t('Kurumsal IA', 'Enterprise IA')}</Badge>,
        supportingPanel: (
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(240px,0.9fr)]">
            <div className="rounded-[22px] border border-border-subtle/70 bg-[var(--surface-card))] p-4 shadow-[0_20px_38px_-30px_var(--shadow-color))]">
              <Text as="div" className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">
                {t('Sabit favoriler', 'Pinned favorites')}
              </Text>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge variant="warning" className="rounded-full">{t('Onaylar', 'Approvals')}</Badge>
                <Badge variant="info" className="rounded-full">{t('Denetim', 'Audit')}</Badge>
                <Badge variant="success" className="rounded-full">{t('Sahipler', 'Owners')}</Badge>
              </div>
              <Text variant="secondary" className="mt-3 text-xs leading-6">
                {t(
                  'Bu yaklaşım kullanıcıların her sayfada aynı kritik rootlara tek tıkla ulaşmasını sağlar.',
                  'This approach lets users reach the same critical roots with one click on every page.',
                )}
              </Text>
            </div>
            <div className="rounded-[22px] border border-border-subtle/70 bg-surface-default p-4">
              <Text as="div" className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">
                {t('Overflow delegasyonu', 'Overflow delegation')}
              </Text>
              <div className="flex flex-col mt-3 gap-2">
                {['analytics', 'exports', 'tokens'].map((entry) => (
                  <div key={entry} className="flex items-center justify-between rounded-2xl border border-border-subtle/70 bg-[var(--surface-card))] px-3 py-2">
                    <Text as="div" preset="body-sm" className="text-sm font-semibold text-text-primary">
                      {entry}
                    </Text>
                    <Badge variant="muted" className="rounded-full">
                      more
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ),
        frameClassName:
          'rounded-[28px] border border-state-warning-text/20/70 bg-[radial-gradient(circle_at_top_left,rgba(254,215,170,0.36),transparent_34%),linear-gradient(180deg,rgba(255,250,245,0.98),var(--surface-default)))] p-4 shadow-[0_34px_72px_-52px_var(--shadow-color))]',
        surfaceClassName:
          'rounded-[24px] border border-state-warning-text/20/70 bg-[var(--surface-card))] p-3 ring-1 ring-[var(--border-subtle)]/20 shadow-[0_22px_36px_-30px_rgba(194,65,12,0.18)]',
      };
    case 'readonly_governance':
      return {
        items: [
          { value: 'review', label: t('Review', 'Review'), href: '/governance/review', icon: <ClipboardList className={iconClassName} /> },
          {
            value: 'approvals',
            label: t('Onaylar', 'Approvals'),
            icon: <Shield className={iconClassName} />,
            menuItems: [
              { key: 'pending', label: t('Bekleyen onaylar', 'Pending approvals'), badge: '4' },
              { key: 'history', label: t('Karar geçmişi', 'Decision history') },
            ],
          },
          { value: 'waivers', label: t('Muafiyetler', 'Waivers'), href: '/governance/waivers', icon: <FileText className={iconClassName} />, badge: '2' },
          { value: 'archive', label: t('Arşiv', 'Archive'), href: '/governance/archive', icon: <BookOpen className={iconClassName} />, disabled: true },
        ],
        appearance: 'outline',
        labelVisibility: 'always',
        access: 'readonly',
        initialValue: 'review',
        endSlot: <Badge variant="muted">{t('Readonly', 'Readonly')}</Badge>,
      };
    case 'analytics_dense':
      return {
        routes: [
          { value: 'dashboards', label: t('Panolar', 'Dashboards'), href: '/analytics/dashboards', icon: <BarChart3 className={iconClassName} />, group: 'primary' },
          {
            value: 'reports',
            label: t('Raporlar', 'Reports'),
            href: '/analytics/reports',
            icon: <ClipboardList className={iconClassName} />,
            group: 'primary',
            emphasis: 'promoted',
            menuItems: [
              { key: 'daily', label: t('Günlük rapor', 'Daily report'), groupLabel: t('Cadence', 'Cadence') },
              { key: 'weekly', label: t('Haftalık rapor', 'Weekly report'), groupLabel: t('Cadence', 'Cadence') },
              { key: 'watchlist', label: t('İzleme listesi', 'Watchlist'), groupLabel: t('Signals', 'Signals'), badge: '4' },
            ],
          },
          { value: 'slices', label: t('Slices', 'Slices'), href: '/analytics/slices', icon: <Activity className={iconClassName} />, group: 'secondary' },
          { value: 'library', label: t('Query library', 'Query library'), href: '/analytics/library', icon: <BookOpen className={iconClassName} />, group: 'utility', emphasis: 'subtle' },
        ],
        appearance: 'outline',
        size: 'sm',
        labelVisibility: 'active',
        initialPath: '/analytics/reports',
        contextTitle: t('Dense analytics workspace', 'Dense analytics workspace'),
        contextDescription: t(
          'MUI veri yoğun dashboard çizgisine daha yakın; badge, grouped submenu ve aktif rapor bağlamını sıkı ritimde taşır.',
          'Closer to dense MUI data dashboards; carries badges, grouped submenus, and active report context in a tighter rhythm.',
        ),
        contextMetrics: [
          { label: t('Aktif rapor', 'Active report'), value: t('Weekly', 'Weekly'), tone: 'success' },
          { label: t('Watchlist', 'Watchlist'), value: '4', tone: 'warning' },
          { label: t('Alan', 'Surface'), value: t('Yoğun', 'Dense'), tone: 'info' },
        ],
        currentBadge: <Badge variant="success">{t('Aktif', 'Active')}</Badge>,
        endSlot: <Badge variant="info">v2</Badge>,
        supportingPanel: (
          <div className="rounded-[22px] border border-border-subtle/70 bg-[var(--surface-card))] p-4 shadow-[0_20px_38px_-30px_var(--shadow-color))]">
            <div className="grid gap-3 md:grid-cols-3">
              {[
                { title: t('Saved view', 'Saved view'), body: t('CFO weekly', 'CFO weekly') },
                { title: t('Segment', 'Segment'), body: t('EMEA / Enterprise', 'EMEA / Enterprise') },
                { title: t('Watch signal', 'Watch signal'), body: t('Latency spike', 'Latency spike') },
              ].map((card) => (
                <div key={card.title} className="rounded-2xl border border-border-subtle/70 bg-surface-default px-3 py-3">
                  <Text as="div" className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">
                    {card.title}
                  </Text>
                  <Text as="div" preset="body-sm" className="mt-1 text-sm font-semibold text-text-primary">
                    {card.body}
                  </Text>
                </div>
              ))}
            </div>
          </div>
        ),
        frameClassName:
          'rounded-[28px] border border-state-info-text/20/70 bg-[radial-gradient(circle_at_top_right,rgba(165,243,252,0.32),transparent_34%),linear-gradient(180deg,rgba(245,252,255,0.98),var(--surface-default)))] p-4 shadow-[0_34px_72px_-52px_var(--shadow-color))]',
      };
    case 'command_hybrid':
      return {
        routes: [
          { value: 'overview', label: t('Genel Bakış', 'Overview'), href: '/ops/overview', icon: <LayoutDashboard className={iconClassName} />, group: 'primary', keywords: ['summary', 'overview'] },
          {
            value: 'lanes',
            label: t('Lane’ler', 'Lanes'),
            href: '/ops/lanes',
            icon: <Workflow className={iconClassName} />,
            group: 'primary',
            emphasis: 'promoted',
            keywords: ['resume', 'pause', 'budget', 'delivery'],
            menuSurfaceTitle: t('Lane command center', 'Lane command center'),
            menuSurfaceDescription: t(
              'Sık kullanılan lane komutlarını ve budget kontrollerini menü açılır yüzeyinde daha zengin biçimde toplar.',
              'Collects high-frequency lane commands and budget checks in a richer flyout surface.',
            ),
            menuSurfaceMeta: (
              <div className="flex flex-wrap gap-2">
                <Badge variant="warning">Queue 4</Badge>
                <Badge variant="info">⌘R / ⌘P</Badge>
              </div>
            ),
            menuItems: [
              { key: 'resume', label: t('Lane devam ettir', 'Resume lane'), groupLabel: t('Delivery', 'Delivery'), shortcut: '⌘R' },
              { key: 'pause', label: t('Lane duraklat', 'Pause lane'), groupLabel: t('Delivery', 'Delivery'), shortcut: '⌘P' },
              { key: 'budget', label: t('Script budget', 'Script budget'), groupLabel: t('Checks', 'Checks'), shortcut: '⌘B' },
            ],
          },
          { value: 'freeze', label: 'Freeze', href: '/ops/freeze', icon: <Shield className={iconClassName} />, badge: 'Hot', group: 'secondary', keywords: ['freeze', 'incident'] },
          { value: 'reports', label: t('Raporlar', 'Reports'), href: '/ops/reports', icon: <FileText className={iconClassName} />, group: 'utility', emphasis: 'subtle', keywords: ['reports', 'evidence'] },
        ],
        appearance: 'outline',
        size: 'sm',
        labelVisibility: 'active',
        enableSearchHandoff: true,
        searchPlaceholder: t('Lane veya komut ara', 'Search lanes or commands'),
        defaultRecentValues: ['lanes', 'freeze'],
        showFavoriteToggle: true,
        defaultFavoriteValues: ['lanes'],
        initialPath: '/ops/lanes',
        contextTitle: t('Ops command hybrid', 'Ops command hybrid'),
        contextDescription: t(
          'Toolbar, search hint ve lane odaklı route geçişini tek bir üst yüzeyde birleştirir. Komut merkezli ekipler için daha hızlıdır.',
          'Combines toolbar, search hint, and lane-focused route switching in a single top surface. It is faster for command-centric teams.',
        ),
        contextMetrics: [
          { label: t('Queue', 'Queue'), value: '4', tone: 'warning' },
          { label: t('Lane', 'Lane'), value: t('Active', 'Active'), tone: 'success' },
          { label: t('Kısayol', 'Shortcut'), value: '⌘K', tone: 'info' },
        ],
        currentBadge: <Badge variant="success">{t('Canlı', 'Live')}</Badge>,
        startSlot: (
          <MenuBarSlotCluster>
            <MenuBarIconChip>
              <Search className={iconClassName} />
            </MenuBarIconChip>
            <Badge variant="muted">⌘K</Badge>
          </MenuBarSlotCluster>
        ),
        endSlot: <Badge variant="warning">Queue 4</Badge>,
        supportingPanel: (
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(220px,0.72fr)]">
            <div className="rounded-[22px] border border-border-subtle/70 bg-[var(--surface-card))] p-4 shadow-[0_20px_38px_-30px_var(--shadow-color))]">
              <Text as="div" className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">
                {t('Önerilen komut akışı', 'Suggested command flow')}
              </Text>
              <div className="mt-3 flex flex-wrap gap-2">
                <Badge variant="info" className="rounded-full">resume lane</Badge>
                <Badge variant="warning" className="rounded-full">pause lane</Badge>
                <Badge variant="success" className="rounded-full">budget</Badge>
              </div>
            </div>
            <div className="rounded-[22px] border border-border-subtle/70 bg-surface-default p-4">
              <Text as="div" className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">
                {t('Yoğunluk nedeni', 'Why dense')}
              </Text>
              <Text variant="secondary" className="mt-2 text-xs leading-6">
                {t(
                  'Komut ağırlıklı ekiplerde üst bar yalnız gezinme değil, operasyon tetikleyici yüzey olarak da davranır.',
                  'In command-heavy teams the top bar acts as an operational trigger surface, not just navigation.',
                )}
              </Text>
            </div>
          </div>
        ),
        frameClassName:
          'rounded-[28px] border border-[var(--border-subtle)]/70 bg-[var(--surface-card),rgba(241,245,249,0.94)))] p-4 shadow-[0_34px_72px_-52px_var(--shadow-color))]',
      };
    case 'subdomain_shell':
      return {
        routes: [
          { value: 'packages', label: t('Packages', 'Packages'), href: '/library/packages', icon: <Package className={iconClassName} />, overflowPriority: 10, group: 'primary', emphasis: 'promoted' },
          {
            value: 'tokens',
            label: t('Tokens', 'Tokens'),
            href: '/library/tokens',
            icon: <Palette className={iconClassName} />,
            overflowPriority: 9,
            group: 'primary',
            menuItems: [
              { key: 'theme', label: t('Theme tokens', 'Theme tokens'), groupLabel: t('Visual', 'Visual') },
              { key: 'motion', label: t('Motion tokens', 'Motion tokens'), groupLabel: t('Visual', 'Visual') },
              { key: 'density', label: t('Density tokens', 'Density tokens'), groupLabel: t('Layout', 'Layout') },
            ],
          },
          { value: 'recipes', label: t('Recipe’ler', 'Recipes'), href: '/library/recipes', icon: <BookOpen className={iconClassName} />, overflowPriority: 8, group: 'secondary' },
          { value: 'patterns', label: t('Pattern’ler', 'Patterns'), href: '/library/patterns', icon: <Sparkles className={iconClassName} />, overflowPriority: 7, group: 'secondary' },
          { value: 'releases', label: t('Sürümler', 'Releases'), href: '/library/releases', icon: <Rocket className={iconClassName} />, overflowPriority: 5, group: 'utility', emphasis: 'subtle' },
          { value: 'docs', label: 'Docs', href: '/library/docs', icon: <FileText className={iconClassName} />, overflowPriority: 4, group: 'utility', emphasis: 'subtle' },
        ],
        appearance: 'default',
        size: 'md',
        labelVisibility: 'always',
        overflowBehavior: 'collapse-to-more',
        overflowLabel: t('Daha fazla', 'More'),
        maxVisibleItems: 4,
        initialPath: '/library/packages',
        contextTitle: t('Subdomain shell navigation', 'Subdomain shell navigation'),
        contextDescription: t(
          'Primer benzeri product shell hissi verir; marka, route ve sürüm bağlamını aynı üst navigasyonda dengeler.',
          'Creates a Primer-like product shell feel by balancing brand, route, and release context in the same top navigation.',
        ),
        contextMetrics: [
          { label: t('Marka', 'Brand'), value: 'Library', tone: 'info' },
          { label: t('Sürüm', 'Release'), value: 'v3.4', tone: 'success' },
          { label: t('Açık rota', 'Active route'), value: t('Packages', 'Packages'), tone: 'warning' },
        ],
        startSlot: <Badge variant="muted">{t('Library', 'Library')}</Badge>,
        currentBadge: <Badge variant="info">{t('Current', 'Current')}</Badge>,
        endSlot: <Badge variant="success">v3.4</Badge>,
        supportingPanel: (
          <div className="rounded-[22px] border border-border-subtle/70 bg-[var(--surface-card))] p-4 shadow-[0_20px_38px_-30px_var(--shadow-color))]">
            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-2xl border border-border-subtle/70 bg-surface-default px-3 py-3">
                <Text as="div" className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">
                  {t('Subdomain denge', 'Subdomain balance')}
                </Text>
                <Text variant="secondary" className="mt-1 text-xs leading-6">
                  {t('Marka alanı route alanını bastırmıyor; bilgi mimarisi okunur kalıyor.', 'The brand area does not dominate the route area; the information architecture stays readable.')}
                </Text>
              </div>
              <div className="rounded-2xl border border-border-subtle/70 bg-surface-default px-3 py-3">
                <Text as="div" className="text-[11px] font-semibold uppercase tracking-[0.18em] text-text-secondary">
                  {t('Version utility', 'Version utility')}
                </Text>
                <Text variant="secondary" className="mt-1 text-xs leading-6">
                  {t('Sürüm ve current badge üst barı kalabalıklaştırmadan görünür kalır.', 'Version and current badges remain visible without crowding the header.')}
                </Text>
              </div>
            </div>
          </div>
        ),
        frameClassName:
          'rounded-[28px] border border-action-primary/20/70 bg-[radial-gradient(circle_at_top_left,rgba(199,210,254,0.34),transparent_34%),linear-gradient(180deg,rgba(248,250,255,0.98),var(--surface-default)))] p-4 shadow-[0_34px_72px_-52px_var(--shadow-color))]',
      };
    case 'theme_contrast':
      return {
        items: [
          { value: 'themes', label: t('Temalar', 'Themes'), icon: <Palette className={iconClassName} /> },
          {
            value: 'contrast',
            label: t('Kontrast', 'Contrast'),
            icon: <Sparkles className={iconClassName} />,
            menuItems: [
              { key: 'soft', label: t('Soft glow', 'Soft glow'), type: 'radio', checked: true },
              { key: 'premium', label: t('Premium glass', 'Premium glass'), type: 'radio' },
            ],
          },
          {
            value: 'motion',
            label: t('Hareket', 'Motion'),
            icon: <Rocket className={iconClassName} />,
            menuItems: [
              { key: 'stagger', label: t('Staggered reveal', 'Staggered reveal'), type: 'checkbox', checked: true },
              { key: 'micro', label: t('Micro motion', 'Micro motion'), type: 'checkbox' },
            ],
          },
          { value: 'ai', label: t('AI yüzeyi', 'AI surface'), icon: <Bot className={iconClassName} /> },
        ],
        appearance: 'ghost',
        size: 'sm',
        labelVisibility: 'active',
        submenuTrigger: 'hover',
        initialValue: 'themes',
        contextTitle: t('Theme contrast utility strip', 'Theme contrast utility strip'),
        contextDescription: t(
          'Ghost yüzey, aktif etiket ve settings-strip yaklaşımını birlikte gösterir. Temalandırma senaryolarında daha hafif bir header sunar.',
          'Combines ghost surface, active labels, and settings-strip behavior. It provides a lighter header for theming scenarios.',
        ),
        startSlot: (
          <MenuBarIconChip>
            <Palette className={iconClassName} />
          </MenuBarIconChip>
        ),
        endSlot: <Badge variant="info">{t('Premium tema', 'Premium theme')}</Badge>,
        frameClassName:
          'rounded-[28px] border border-action-primary/20/70 bg-[radial-gradient(circle_at_top_right,rgba(245,208,254,0.34),transparent_34%),linear-gradient(180deg,rgba(253,244,255,0.98),var(--surface-default)))] p-4 shadow-[0_34px_72px_-52px_var(--shadow-color))]',
      };
  }
};

const InteractiveMenuBarSurface: React.FC<{
  variantId: MenuBarVariantId;
  ariaLabel?: string;
  locale: string;
}> = ({ variantId, ariaLabel, locale }) => {
  const config = React.useMemo(() => buildInteractiveVariantConfig(variantId, locale), [locale, variantId]);
  const isTurkish = locale.startsWith('tr');
  const [selectedValue, setSelectedValue] = React.useState(
    config.initialValue ?? config.routes?.[0]?.value ?? config.items?.[0]?.value ?? '',
  );
  const [currentPath, setCurrentPath] = React.useState(
    config.initialPath ?? config.routes?.find((route) => typeof route.href === 'string')?.href ?? '',
  );
  const [favoriteValues, setFavoriteValues] = React.useState<string[]>(config.defaultFavoriteValues ?? []);
  const [recentValues, setRecentValues] = React.useState<string[]>(config.defaultRecentValues ?? []);
  const [lastAction, setLastAction] = React.useState<string | null>(null);

  React.useEffect(() => {
    setFavoriteValues(config.defaultFavoriteValues ?? []);
    setRecentValues(config.defaultRecentValues ?? []);
  }, [config.defaultFavoriteValues, config.defaultRecentValues, variantId]);

  const resolvedItems = React.useMemo(
    () =>
      config.routes
        ? createMenuBarItemsFromRoutes(config.routes, {
            currentValue: selectedValue || undefined,
            currentPath: currentPath || undefined,
            currentBadge: config.currentBadge as string,
          })
        : config.items ?? [],
    [config.currentBadge, config.items, config.routes, currentPath, selectedValue],
  );

  const handleItemClick = React.useCallback(
    (value: string, event: React.MouseEvent<HTMLElement>) => {
      const nextHref = resolveHrefForValue(value, resolvedItems, config.routes ?? []);
      if (nextHref) {
        event.preventDefault();
        setCurrentPath(nextHref);
      }
      setSelectedValue(value);
      const label = getNodeText(resolvedItems.find((item) => item.value === value)?.label ?? value) || value;
      setLastAction(label);
    },
    [config.routes, resolvedItems],
  );

  const handleMenuItemSelect = React.useCallback(
    (rootValue: string, item: MenuBarMenuItem) => {
      setSelectedValue(rootValue);
      const rootLabel = getNodeText(resolvedItems.find((entry) => entry.value === rootValue)?.label ?? rootValue) || rootValue;
      const actionLabel = getNodeText(item.label) || item.key;
      setLastAction(`${rootLabel} · ${actionLabel}`);
    },
    [resolvedItems],
  );

  return (
    <div className={config.frameClassName ?? 'gap-4'}>
      {config.contextTitle || config.contextDescription || config.contextMetrics?.length ? (
        <div className="flex flex-col gap-3">
          {config.contextTitle || config.contextDescription ? (
            <div className="flex flex-col gap-1">
              {config.contextTitle ? (
                <Text as="div" preset="body-sm" className="text-base font-semibold text-text-primary">
                  {config.contextTitle as string}
                </Text>
              ) : null}
              {config.contextDescription ? (
                <Text variant="secondary" className="block text-sm leading-7">
                  {config.contextDescription as string}
                </Text>
              ) : null}
            </div>
          ) : null}
          {config.contextMetrics?.length ? (
            <div className="grid gap-2 sm:grid-cols-3">
              {config.contextMetrics.map((metric, index) => (
                <MenuBarMetricChip
                  key={`${variantId}-metric-${index}`}
                  label={metric.label}
                  value={metric.value}
                  tone={metric.tone}
                />
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
      <div className={config.surfaceClassName ?? config.wrapperClassName ?? 'rounded-[26px] border border-border-subtle bg-surface-canvas p-3'}>
        <MenuBar
          ariaLabel={ariaLabel}
          items={resolvedItems}
          value={selectedValue}
          currentPath={currentPath || undefined}
          onValueChange={setSelectedValue}
          onItemClick={handleItemClick}
          onMenuItemSelect={handleMenuItemSelect}
          startSlot={config.startSlot as string}
          endSlot={config.endSlot as string}
          access={config.access ?? 'full'}
          size={config.size ?? 'md'}
          appearance={config.appearance ?? 'default'}
          labelVisibility={config.labelVisibility ?? 'always'}
          labelCollapseBreakpoint={config.labelCollapseBreakpoint}
          overflowBehavior={config.overflowBehavior}
          overflowLabel={config.overflowLabel}
          maxVisibleItems={config.maxVisibleItems}
          showFavoriteToggle={config.showFavoriteToggle}
          favoriteValues={favoriteValues}
          onFavoriteValuesChange={setFavoriteValues}
          recentValues={recentValues}
          onRecentValuesChange={setRecentValues}
          recentLimit={config.recentLimit}
          enableSearchHandoff={config.enableSearchHandoff}
          searchPlaceholder={config.searchPlaceholder}
          searchEmptyStateLabel={config.searchEmptyStateLabel}
          submenuTrigger={config.submenuTrigger}
          responsiveBreakpoint={config.responsiveBreakpoint}
          mobileFallback={config.mobileFallback}
          utilityCollapse={config.utilityCollapse}
        />
        <div className="mt-3 flex items-center justify-between gap-3">
          <div className="flex flex-col gap-2">
            <Text variant="secondary" className="text-xs leading-6">
              {lastAction
                ? `${isTurkish ? 'Son seçim' : 'Last selection'}: ${lastAction}`
                : isTurkish
                  ? 'Bir root ya da submenu seçerek etkileşimi izle.'
                  : 'Select a root or submenu item to inspect the interaction.'}
            </Text>
            {config.showFavoriteToggle || config.enableSearchHandoff ? (
              <div className="flex flex-wrap gap-2">
                {config.showFavoriteToggle ? (
                  <Badge variant="warning" className="rounded-full">
                    {(isTurkish ? 'Favoriler' : 'Favorites') + `: ${favoriteValues.length}`}
                  </Badge>
                ) : null}
                {config.enableSearchHandoff ? (
                  <Badge variant="muted" className="rounded-full">
                    {(isTurkish ? 'Recent' : 'Recent') + `: ${recentValues.length}`}
                  </Badge>
                ) : null}
              </div>
            ) : null}
          </div>
          <div className="flex flex-wrap justify-end gap-2">
            {currentPath ? (
              <Badge variant="info" className="rounded-full">
                {currentPath}
              </Badge>
            ) : null}
            {config.enableSearchHandoff ? (
              <Badge variant="success" className="rounded-full">
                {config.searchPlaceholder ?? (isTurkish ? 'Arama açık' : 'Search ready')}
              </Badge>
            ) : null}
          </div>
        </div>
      </div>
      {config.supportingPanel ? config.supportingPanel : null}
    </div>
  );
};

export const DesignLabMenuBarVariantPreview: React.FC<DesignLabMenuBarPreviewProps> = ({
  variantId,
  ariaLabel = 'Menu bar preview',
  locale = 'tr',
}) => <InteractiveMenuBarSurface variantId={variantId} ariaLabel={ariaLabel} locale={locale} />;
