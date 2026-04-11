import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  GroupedCardGallery,
  GalleryCard,
} from '@mfe/design-system';
import type { GalleryItem } from '@mfe/design-system';
import { usePermissions } from '@mfe/auth';
import { useCatalog, catalogTypeTone } from './useCatalog';
import type { CatalogItem } from './useCatalog';

/* ------------------------------------------------------------------ */
/*  Constants                                                          */
/* ------------------------------------------------------------------ */

const resolveBasePath = (pathname: string): string =>
  pathname.startsWith('/admin/reports') ? '/admin/reports' : '/reports';

const GROUP_ORDER = [
  '\u0130nsan Kaynaklar\u0131',
  'Denetim',
  'Erisim & Guvenlik',
  'Finans',
  'Operasyon',
  'Sat\u0131\u015F',
  'IT',
  'Dashboard',
  'Diger',
  'Genel',
];

const GROUP_ICONS: Record<string, string> = {
  'Denetim': '\uD83D\uDCCB',
  'Erisim & Guvenlik': '\uD83D\uDD10',
  'Finans': '\uD83D\uDCB0',
  'Operasyon': '\u2699\uFE0F',
  'IT': '\uD83D\uDCBB',
  'Dashboard': '\uD83D\uDCCA',
  'Diger': '\uD83D\uDCC2',
  'Genel': '\uD83D\uDCC4',
  '\u0130nsan Kaynaklar\u0131': '\uD83D\uDC65',
  'Sat\u0131\u015F': '\uD83D\uDED2',
};

const DEBOUNCE_MS = 250;

/* ------------------------------------------------------------------ */
/*  Search helper                                                      */
/* ------------------------------------------------------------------ */

function filterItems(items: CatalogItem[], query: string): CatalogItem[] {
  if (!query) return items;
  const lower = query.toLowerCase();
  return items.filter((item) => {
    if (item.title.toLowerCase().includes(lower)) return true;
    if (item.description?.toLowerCase().includes(lower)) return true;
    if (item.tags?.some((t) => t.toLowerCase().includes(lower))) return true;
    if (item.category.toLowerCase().includes(lower)) return true;
    return false;
  });
}

/* ------------------------------------------------------------------ */
/*  ReportingHub                                                       */
/* ------------------------------------------------------------------ */

const ReportingHub: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const basePath = resolveBasePath(location.pathname);
  const { items, isLoading } = useCatalog();
  const { canViewReport, isSuperAdmin } = usePermissions();
  const inputRef = useRef<HTMLInputElement>(null);

  /* -- Search -------------------------------------------------------- */
  const [inputValue, setInputValue] = useState('');
  const [query, setQuery] = useState('');

  useEffect(() => {
    const timer = setTimeout(() => setQuery(inputValue), DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [inputValue]);

  // Cmd+K / Ctrl+K shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // TB-14/18: Filter by reportGroup using canViewReport (deny-default coarse gate)
  const authorizedItems = useMemo(() => {
    if (isSuperAdmin()) return items;
    return items.filter((item) => !item.reportGroup || canViewReport(item.reportGroup));
  }, [items, canViewReport, isSuperAdmin]);

  const filteredItems = useMemo(() => filterItems(authorizedItems, query), [authorizedItems, query]);

  /* -- Summary ------------------------------------------------------- */
  const summary = useMemo(() => {
    const dashCount = authorizedItems.filter((i) => i.type === 'dashboard').length;
    const reportCount = authorizedItems.length - dashCount;
    const parts: string[] = [];
    if (reportCount > 0) parts.push(`${reportCount} rapor`);
    if (dashCount > 0) parts.push(`${dashCount} dashboard`);
    return parts.join(' \u00B7 ') || `${items.length} oge`;
  }, [authorizedItems]);

  /* -- Handlers ------------------------------------------------------ */
  const handleItemClick = useCallback(
    (item: GalleryItem) => {
      navigate(`${basePath}/${(item as CatalogItem).route}`);
    },
    [navigate, basePath],
  );

  const renderCard = useCallback(
    (item: GalleryItem) => {
      const ci = item as CatalogItem;
      return (
        <GalleryCard
          item={{
            ...ci,
            badge: {
              label: ci.type === 'dashboard' ? 'Dashboard' : 'Grid',
              tone: catalogTypeTone[ci.type] ?? 'default',
            },
          }}
          onClick={() => handleItemClick(ci)}
        />
      );
    },
    [handleItemClick],
  );

  const summaryFormatter = useCallback(
    (all: GalleryItem[], filtered: GalleryItem[]) => {
      if (filtered.length < all.length) {
        return `${filtered.length} / ${all.length} sonuc`;
      }
      return '';
    },
    [],
  );

  /* -- Loading ------------------------------------------------------- */
  if (isLoading && items.length === 0) {
    return (
      <div className="flex flex-col items-center gap-6 px-6 pt-16">
        <div className="h-8 w-48 animate-pulse rounded-xl bg-surface-muted" />
        <div className="h-10 w-full max-w-lg animate-pulse rounded-2xl bg-surface-muted" />
        <div className="mt-4 grid w-full max-w-5xl grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-32 animate-pulse rounded-2xl bg-surface-muted" />
          ))}
        </div>
      </div>
    );
  }

  const isSearching = query.length > 0;

  return (
    <div className="flex flex-col gap-8">
      {/* ---- Hero header ---- */}
      <div className="flex flex-col items-center gap-4 pb-2 pt-10">
        {/* Title */}
        <h1 className="text-3xl font-extrabold tracking-tight text-text-primary sm:text-4xl">
          Raporlar
        </h1>

        {/* Description */}
        <p className="max-w-md text-center text-sm text-text-secondary">
          Tum raporlar ve dashboard'lara buradan ulasabilirsiniz.
        </p>

        {/* Search — command-palette style */}
        <div className="relative w-full max-w-lg">
          <svg
            className="pointer-events-none absolute start-3.5 top-1/2 h-[18px] w-[18px] -translate-y-1/2 text-text-secondary"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>

          <input
            ref={inputRef}
            type="search"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Tum raporlarda ara..."
            className="w-full rounded-2xl border border-border-subtle bg-surface-default py-2.5 pe-16 ps-10 text-sm text-text-primary shadow-xs transition placeholder:text-text-disabled hover:bg-surface-muted focus:border-action-primary focus:outline-hidden focus:ring-2 focus:ring-action-primary/20 [&::-webkit-search-cancel-button]:hidden"
            aria-label="Rapor ara"
          />

          {/* Shortcut badge or clear button */}
          {isSearching ? (
            <button
              type="button"
              onClick={() => { setInputValue(''); setQuery(''); }}
              className="absolute end-3 top-1/2 -translate-y-1/2 rounded-md p-1 text-text-secondary transition hover:text-text-primary"
              aria-label="Temizle"
            >
              <svg className="h-4 w-4" viewBox="0 0 16 16" fill="none">
                <path d="M12 4L4 12M4 4l8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </button>
          ) : (
            <kbd className="absolute end-3 top-1/2 -translate-y-1/2 rounded-lg border border-border-subtle bg-surface-panel px-2 py-0.5 text-[10px] font-semibold text-text-subtle">
              {'\u2318'}K
            </kbd>
          )}
        </div>

        {/* Filtered summary */}
        {isSearching && (
          <p className="text-xs text-text-secondary">
            {filteredItems.length} / {items.length} sonuc
          </p>
        )}
      </div>

      {/* ---- Card gallery ---- */}
      <div className="mx-auto w-full max-w-6xl px-4">
        <GroupedCardGallery
          key={isSearching ? 'search' : 'browse'}
          items={filteredItems}
          groupBy="category"
          hideSearch
          defaultExpandedGroups={isSearching ? [...new Set(filteredItems.map((i) => i.category))] : GROUP_ORDER.slice(0, 3)}
          groupOrder={GROUP_ORDER}
          onItemClick={handleItemClick}
          renderCard={renderCard}
          summaryFormatter={summaryFormatter}
          storageKey={isSearching ? undefined : 'reporting-hub-groups'}
          groupIcons={GROUP_ICONS}
        />
      </div>
    </div>
  );
};

export default ReportingHub;
