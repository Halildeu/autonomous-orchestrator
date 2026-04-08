import { useState, useCallback, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import type { CommandPaletteItem } from '@mfe/design-system';
import { usePermissions } from '@mfe/auth';
import { useAuthorization } from '../../../features/auth/model/use-authorization.model';
import { useAppSelector, useAppDispatch } from '../../store/store.hooks';
import { toggleOpen } from '../../../features/notifications/model/notifications.slice';
import {
  isSuggestionsRemoteEnabled,
  isEthicRemoteEnabled,
} from '../../shell-navigation';
import { useShellCommonI18n } from '../../i18n';
import { SEARCHABLE_ITEMS, SEARCH_GROUP_LABELS, type SearchableItem } from './header-search.config';
import { useRecentPages } from './useRecentPages';
import { nlSearch } from './nl-search-engine';

/* ------------------------------------------------------------------ */
/*  Hook                                                               */
/* ------------------------------------------------------------------ */

export interface GlobalSearchState {
  isOpen: boolean;
  open: () => void;
  close: () => void;
  items: CommandPaletteItem[];
  query: string;
  setQuery: (q: string) => void;
  handleSelect: (id: string) => void;
  groupLabels: Record<string, string>;
}

export function useGlobalSearch(): GlobalSearchState {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const navigate = useNavigate();
  const dispatch = useAppDispatch();
  const { hasModule, isSuperAdmin } = usePermissions();
  const { hasPermission } = useAuthorization(); // legacy compat for search items
  const { initialized } = useAppSelector((s) => s.auth);
  const { t, manager: i18nManager } = useShellCommonI18n();
  const suggestionsEnabled = isSuggestionsRemoteEnabled();
  const ethicEnabled = isEthicRemoteEnabled();
  const { recentPages } = useRecentPages();

  const open = useCallback(() => { setIsOpen(true); setQuery(''); }, []);
  const close = useCallback(() => { setIsOpen(false); setQuery(''); }, []);

  // Ctrl+K / Cmd+K global shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setIsOpen((prev) => !prev);
        if (!isOpen) setQuery('');
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen]);

  // Filter searchable items by permission and remote flags
  const filteredItems = useMemo<SearchableItem[]>(() => {
    if (!initialized) return [];
    return SEARCHABLE_ITEMS.filter((item) => {
      if (item.remoteFlag === 'suggestions' && !suggestionsEnabled) return false;
      if (item.remoteFlag === 'ethic' && !ethicEnabled) return false;
      if (item.permission && !hasPermission(item.permission)) return false;
      return true;
    });
  }, [initialized, hasPermission, suggestionsEnabled, ethicEnabled]);

  // Build CommandPalette items: recent + filtered
  const items = useMemo<CommandPaletteItem[]>(() => {
    const result: CommandPaletteItem[] = [];

    // Recent pages (only when no query — shown immediately on open)
    if (!query.trim()) {
      for (const rp of recentPages) {
        result.push({
          id: rp.id,
          title: rp.path,
          group: t(SEARCH_GROUP_LABELS.recent),
          keywords: rp.keywords,
        });
      }
    }

    const standardIds = new Set<string>();
    for (const item of filteredItems) {
      standardIds.add(item.id);
      result.push({
        id: item.id,
        title: t(item.titleKey),
        description: item.descriptionKey ? t(item.descriptionKey) : undefined,
        group: t(SEARCH_GROUP_LABELS[item.group]),
        shortcut: item.shortcut,
        keywords: item.keywords,
      });
    }

    // AI-augmented NL search: append smart suggestions when query is non-empty
    if (query.trim().length >= 2) {
      const nlMatches = nlSearch(query, filteredItems);
      const smartGroupLabel = t('shell.search.group.smartSuggestions');
      for (const match of nlMatches) {
        if (!standardIds.has(match.item.id)) continue; // only suggest from filtered items
        result.push({
          id: `nl-${match.item.id}`,
          title: t(match.item.titleKey),
          description: match.matchReason || undefined,
          group: smartGroupLabel,
          keywords: match.item.keywords,
        });
      }
    }

    return result;
  }, [filteredItems, recentPages, query, t]);

  // Translated group labels for display
  const groupLabels = useMemo(() => {
    const labels: Record<string, string> = {};
    for (const [key, labelKey] of Object.entries(SEARCH_GROUP_LABELS)) {
      labels[key] = t(labelKey);
    }
    return labels;
  }, [t]);

  // Handle selection
  const handleSelect = useCallback(
    (id: string) => {
      close();

      // NL smart suggestion — strip prefix and re-route
      if (id.startsWith('nl-')) {
        handleSelect(id.slice(3));
        return;
      }

      // Recent page
      if (id.startsWith('recent-')) {
        const rp = recentPages.find((r) => r.id === id);
        if (rp?.path) navigate(rp.path);
        return;
      }

      // Commands
      if (id === 'cmd-theme-toggle') {
        // Dispatch theme panel toggle via custom event
        window.dispatchEvent(new CustomEvent('shell:toggle-theme-panel'));
        return;
      }
      if (id === 'cmd-lang-tr' || id === 'cmd-lang-en') {
        const locale = id === 'cmd-lang-tr' ? 'tr' : 'en';
        i18nManager.setLocale(locale);
        try {
          window.localStorage.setItem('mfe.locale', locale);
          window.dispatchEvent(new CustomEvent('app:locale-change', { detail: { locale } }));
        } catch { /* ignore */ }
        return;
      }
      if (id === 'cmd-notifications') {
        dispatch(toggleOpen(true));
        return;
      }

      // Navigation / Reports / Tools — find item with path
      const allItems = [...SEARCHABLE_ITEMS, ...recentPages];
      const item = allItems.find((i) => i.id === id);
      if (item?.path) navigate(item.path);
    },
    [close, navigate, dispatch, i18nManager, recentPages],
  );

  return { isOpen, open, close, items, query, setQuery, handleSelect, groupLabels };
}
