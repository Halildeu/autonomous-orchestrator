import { useState, useEffect, useMemo } from 'react';
import {
  listSharedReportsForChannel,
  type SharedReportCatalogItem,
} from '@platform/capabilities';
import {
  fetchReportList,
  type ReportListItem,
} from '../../modules/dynamic-report';
import {
  fetchDashboardList,
  type DashboardListItem,
} from '../../modules/dashboard';
import { reportModules } from '../../modules';
import type { GalleryItem } from '@mfe/design-system';

/* ------------------------------------------------------------------ */
/*  CatalogItem — extends GalleryItem for the reporting hub            */
/* ------------------------------------------------------------------ */

export interface CatalogItem extends GalleryItem {
  type: 'grid' | 'dashboard' | 'mixed';
  category: string;
  source: 'static' | 'dynamic' | 'dashboard';
  route: string;
}

/* ------------------------------------------------------------------ */
/*  Type colors for badge rendering                                    */
/* ------------------------------------------------------------------ */

export const catalogTypeTone: Record<string, string> = {
  grid: 'primary',
  dashboard: 'info',
  mixed: 'warning',
};

/* ------------------------------------------------------------------ */
/*  Mappers                                                            */
/* ------------------------------------------------------------------ */

function mapStatic(report: SharedReportCatalogItem): CatalogItem {
  return {
    id: report.id,
    title: report.title,
    description: report.description,
    group: report.category ?? 'Genel',
    icon: report.icon ?? '📋',
    tags: report.tags ? [...report.tags] : [],
    badge: {
      label: report.type === 'dashboard' ? 'Dashboard' : 'Grid',
      tone: catalogTypeTone[report.type ?? 'grid'],
    },
    route: report.webRouteSegment,
    type: report.type ?? 'grid',
    category: report.category ?? 'Genel',
    source: 'static',
  };
}

function mapDynamic(report: ReportListItem): CatalogItem {
  return {
    id: `dynamic-${report.key}`,
    title: report.title,
    description: report.description,
    group: report.category || 'Diger',
    icon: '📊',
    tags: [],
    badge: { label: 'Grid', tone: 'primary' },
    route: report.key,
    type: 'grid',
    category: report.category || 'Diger',
    source: 'dynamic',
  };
}

function mapDashboard(db: DashboardListItem): CatalogItem {
  return {
    id: `dashboard-${db.key}`,
    title: db.title,
    description: db.description,
    group: db.category || 'Dashboard',
    icon: db.icon || '📈',
    tags: [],
    badge: { label: 'Dashboard', tone: 'info' },
    route: `dashboard-${db.key}`,
    type: 'dashboard',
    category: db.category || 'Dashboard',
    source: 'dashboard',
  };
}

/* ------------------------------------------------------------------ */
/*  useCatalog                                                         */
/* ------------------------------------------------------------------ */

export function useCatalog() {
  const [dynamicReports, setDynamicReports] = useState<ReportListItem[]>([]);
  const [dashboards, setDashboards] = useState<DashboardListItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Static reports — instant, no async needed
  const staticItems = useMemo(() => {
    return listSharedReportsForChannel('web').map(mapStatic);
  }, []);

  // Fetch dynamic reports + dashboards
  useEffect(() => {
    let active = true;
    Promise.all([
      fetchReportList().catch((err) => {
        console.warn('[useCatalog] dynamic report list failed:', err);
        return [] as ReportListItem[];
      }),
      fetchDashboardList().catch((err) => {
        console.warn('[useCatalog] dashboard list failed:', err);
        return [] as DashboardListItem[];
      }),
    ]).then(([reports, dbs]) => {
      if (active) {
        setDynamicReports(reports);
        setDashboards(dbs);
        setIsLoading(false);
      }
    });
    return () => { active = false; };
  }, []);

  // Merge all sources — deduplicate by route
  const items = useMemo<CatalogItem[]>(() => {
    const staticRoutes = new Set(staticItems.map((s) => s.route));

    const dynamicItems = dynamicReports
      .filter((r) => !staticRoutes.has(r.key))
      .map(mapDynamic);

    const allRoutes = new Set([
      ...staticRoutes,
      ...dynamicItems.map((d) => d.route),
    ]);

    const dashboardItems = dashboards
      .filter((db) => !allRoutes.has(`dashboard-${db.key}`))
      .map(mapDashboard);

    // Extra modules registered in reportModuleMap but not in any catalog source
    const allFinalRoutes = new Set([
      ...staticRoutes,
      ...dynamicItems.map((d) => d.route),
      ...dashboardItems.map((d) => d.route),
    ]);
    const extraItems: CatalogItem[] = reportModules
      .filter((m) => !allFinalRoutes.has(m.route))
      .map((m) => ({
        id: m.id,
        title: m.titleKey,
        description: m.descriptionKey ?? '',
        group: 'Dashboard',
        icon: '🔍',
        tags: [],
        badge: { label: 'Dashboard', tone: 'info' },
        route: m.route,
        type: 'dashboard' as const,
        category: 'Dashboard',
        source: 'static' as const,
      }));

    return [...staticItems, ...dynamicItems, ...dashboardItems, ...extraItems];
  }, [staticItems, dynamicReports, dashboards]);

  return { items, isLoading };
}
