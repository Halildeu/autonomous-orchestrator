/**
 * VariantIntegration — Grid variant save/load/clone with personal/global management.
 *
 * Responsibilities:
 * - Connects to useGridVariants hook (lib/grid-variants)
 * - Collects grid column/filter/sort state via GridApi
 * - Applies saved variant state to grid
 * - Provides variant dropdown selector (optgroup: personal/global)
 * - Provides compact accordion-based variant manager panel
 * - Handles variant CRUD, promote/demote, default management
 *
 * v34 API notes:
 * - getColumnState() / applyColumnState() on GridApi (not ColumnApi)
 * - getFilterModel() / setFilterModel()
 * - getAdvancedFilterModel() / setAdvancedFilterModel()
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { resolveAccessState, accessStyles, type AccessControlledProps } from '../../internal/access-controller';
import type { GridApi, ColumnState, AdvancedFilterModel } from "ag-grid-community";
import {
  fetchGridVariants,
  createGridVariant,
  updateGridVariant,
  cloneGridVariant,
  deleteGridVariant,
  updateVariantPreference,
  compareGridVariants,
} from "../../lib/grid-variants";
import { cn } from "../../utils/cn";
import { useAccordion } from "../../headless/hooks/useAccordion";
import { IconSettings } from "../../icons/user/IconSettings";
import { IconClose } from "../../icons/action/IconClose";
import { IconSave } from "../../icons/action/IconSave";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------
 */

export interface GridVariantState {
  columnState?: unknown[];
  filterModel?: Record<string, unknown>;
  advancedFilterModel?: unknown;
  sortModel?: unknown[];
  pivotMode?: boolean;
  quickFilterText?: string;
  paginationPageSize?: number;
}

export interface GridVariant {
  id: string;
  gridId: string;
  name: string;
  state: GridVariantState;
  isDefault?: boolean;
  isGlobal?: boolean;
  isGlobalDefault?: boolean;
  isUserDefault?: boolean;
  isUserSelected?: boolean;
  isCompatible?: boolean;
  schemaVersion?: number;
  sortOrder?: number;
  createdAt?: string;
  updatedAt?: string;
}

export interface VariantIntegrationMessages {
  variantLabel?: string;
  variantPlaceholder?: string;
  variantNewButtonLabel?: string;
  variantNamePlaceholder?: string;
  variantModalTitle?: string;
  defaultVariantName?: string;
  // Section headers
  personalVariantsTitle?: string;
  globalVariantsTitle?: string;
  personalVariantsEmptyLabel?: string;
  globalVariantsEmptyLabel?: string;
  // Actions
  menuSelectLabel?: string;
  menuRenameLabel?: string;
  menuSetDefaultLabel?: string;
  menuUnsetDefaultLabel?: string;
  menuSetGlobalDefaultLabel?: string;
  menuUnsetGlobalDefaultLabel?: string;
  menuMoveToGlobalLabel?: string;
  menuMoveToPersonalLabel?: string;
  menuDeleteLabel?: string;
  saveCurrentStateLabel?: string;
  saveLabel?: string;
  cancelLabel?: string;
  // Tags
  selectedTagLabel?: string;
  personalTagLabel?: string;
  personalDefaultTagLabel?: string;
  globalPublicTagLabel?: string;
  globalPublicDefaultTagLabel?: string;
  incompatibleTagLabel?: string;
  // Detail
  showDetailsLabel?: string;
  hideDetailsLabel?: string;
  variantActionsLabel?: string;
  moveToPersonalTitle?: string;
  moveToGlobalTitle?: string;
  saveCurrentLayoutTitle?: string;
  saveTitle?: string;
  // Feedback
  variantSavedLabel?: string;
  variantSaveFailedLabel?: string;
  variantCreatedLabel?: string;
  variantCreateFailedLabel?: string;
  variantDeletedLabel?: string;
  variantDeleteFailedLabel?: string;
  variantPromotedToGlobalLabel?: string;
  variantDemotedToPersonalLabel?: string;
  variantGlobalStatusUpdateFailedLabel?: string;
  defaultViewEnabledLabel?: string;
  defaultViewDisabledLabel?: string;
  defaultStateUpdateFailedLabel?: string;
  deleteVariantConfirmationLabel?: string;
  closeVariantManagerLabel?: string;
  variantNameEmptyLabel?: string;
  variantNameUpdatedLabel?: string;
  variantNameUpdateFailedLabel?: string;
  variantPreferenceUpdateFailedLabel?: string;
}

/** Props for the VariantIntegration component. */
export interface VariantIntegrationProps<RowData = unknown> extends AccessControlledProps {
  /** Grid ID for variant isolation */
  gridId: string;
  /** Grid schema version for compatibility check */
  gridSchemaVersion: number;
  /** Reference to current GridApi */
  gridApi: GridApi<RowData> | null;
  /** Active variant ID */
  activeVariantId?: string;
  /** Variant change callback */
  onActiveVariantChange?: (variantId: string | null) => void;
  /** i18n messages */
  messages?: VariantIntegrationMessages;
  /** Whether the current user can promote personal variants to global */
  canPromoteToGlobal?: boolean;
  /** Whether the current user can demote global variants to personal */
  canDemoteToPersonal?: boolean;
  /** Whether the current user can delete global variants */
  canDeleteGlobal?: boolean;
  /** Additional CSS class for custom styling */
  className?: string;
}

/* ------------------------------------------------------------------ */
/*  State collection (v34 GridApi)                                     */
/* ------------------------------------------------------------------ */

function collectGridState<RowData>(api: GridApi<RowData>): GridVariantState {
  return {
    columnState: api.getColumnState?.() ?? [],
    filterModel: api.getFilterModel?.() ?? {},
    advancedFilterModel: api.getAdvancedFilterModel?.() ?? null,
    sortModel: (api.getColumnState?.() ?? [])
      .filter((c) => c.sort)
      .map((c) => ({
        colId: c.colId,
        sort: c.sort!,
        sortIndex: c.sortIndex,
      })),
    pivotMode: api.isPivotMode?.() ?? false,
    quickFilterText: (api.getGridOption?.("quickFilterText") as string) ?? "",
    paginationPageSize: (api.getGridOption?.("paginationPageSize") as number) ?? undefined,
  };
}

function applyVariantState<RowData>(api: GridApi<RowData>, state: GridVariantState): void {
  if (state.columnState && Array.isArray(state.columnState)) {
    api.applyColumnState?.({ state: state.columnState as ColumnState[], applyOrder: true, defaultState: { hide: false } });
  }
  // Always apply filter model — null/undefined/{} clears existing filters
  api.setFilterModel?.(state.filterModel ?? null);
  if (state.advancedFilterModel !== undefined) {
    api.setAdvancedFilterModel?.(state.advancedFilterModel as AdvancedFilterModel);
  } else {
    // Clear advanced filter if variant has none
    api.setAdvancedFilterModel?.(null as unknown as AdvancedFilterModel);
  }
  if (typeof state.pivotMode === "boolean") {
    api.setGridOption?.("pivotMode", state.pivotMode);
  }
  if (typeof state.quickFilterText === "string") {
    api.setGridOption?.("quickFilterText", state.quickFilterText);
  }
  if (typeof state.paginationPageSize === "number" && state.paginationPageSize > 0) {
    api.setGridOption?.("paginationPageSize", state.paginationPageSize);
  }
  // Refresh SSRM after applying variant state so filters/sort take effect
  const rowModelType = api.getGridOption?.("rowModelType");
  if (rowModelType === "serverSide") {
    api.refreshServerSide?.({ purge: true });
  }
}

function dispatchVariantToast(type: "error" | "success" | "warning" | "info", text: string): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.dispatchEvent(new CustomEvent("app:toast", { detail: { type, text } }));
  } catch {
    // ignore toast dispatch failures in non-browser or test runtimes
  }
}

/* ------------------------------------------------------------------ */
/*  Chevron icon                                                       */
/* ------------------------------------------------------------------ */

function ChevronIcon({ expanded }: { expanded: boolean }) {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      className={cn(
        "shrink-0 transition-[rotate] duration-(--motion-duration-fast)",
        expanded && "rotate-90",
      )}
    >
      <path d="M4.5 2.5L8 6L4.5 9.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

/** Grid variant manager for saving, loading, and switching named column/filter configurations. 
 * @example
 * ```tsx
 * <VariantIntegration />
 * ```
 * @since 1.0.0
 * @see [Docs](https://design.mfe.dev/components/variant-integration)
 */
export const VariantIntegration = <RowData = unknown,>({
  gridId,
  gridSchemaVersion,
  gridApi,
  activeVariantId: controlledVariantId,
  onActiveVariantChange,
  messages,
  canPromoteToGlobal = false,
  canDemoteToPersonal = false,
  canDeleteGlobal = false,
  access,
  accessReason,
}: VariantIntegrationProps<RowData>): React.ReactElement => {
  const accessState = resolveAccessState(access);
  if (accessState.isHidden) return <></> as unknown as React.ReactElement;
  // ── Core state ─────────────────────────────────────────────────────
  const [variants, setVariants] = useState<GridVariant[]>([]);
  const [internalActiveId, setInternalActiveId] = useState<string | null>(controlledVariantId ?? null);
  const [loading, setLoading] = useState(false);
  const [newVariantName, setNewVariantName] = useState("");
  const [showManager, setShowManager] = useState(false);
  const appliedRef = useRef<string | null>(null);

  // ── Manager panel state ────────────────────────────────────────────
  const [renamingVariantId, setRenamingVariantId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  const activeId = controlledVariantId ?? internalActiveId;
  const m = messages ?? {};

  // ── Accordion ──────────────────────────────────────────────────────
  const accordion = useAccordion({ multiple: false });

  // ── Derived lists ──────────────────────────────────────────────────
  const personalVariants = useMemo(
    () => variants.filter((v) => !v.isGlobal).sort(compareGridVariants as (a: GridVariant, b: GridVariant) => number),
    [variants],
  );
  const globalVariants = useMemo(
    () => variants.filter((v) => v.isGlobal).sort(compareGridVariants as (a: GridVariant, b: GridVariant) => number),
    [variants],
  );

  // ── Fetch variants ─────────────────────────────────────────────────
  const loadVariants = useCallback(async () => {
    try {
      setLoading(true);
      const result = await fetchGridVariants(gridId);
      if (Array.isArray(result)) {
        setVariants(result as GridVariant[]);
      }
    } catch {
      // Graceful degradation — grid works without variants
    } finally {
      setLoading(false);
    }
  }, [gridId]);

  useEffect(() => {
    loadVariants();
  }, [loadVariants]);

  // ── Auto-apply on first load ───────────────────────────────────────
  useEffect(() => {
    if (!gridApi || variants.length === 0 || appliedRef.current) return;

    // Priority: requested initial variant → user selected → user default → global default → first compatible
    const requested = activeId
      ? variants.find((v) => v.id === activeId && v.isCompatible !== false)
      : null;
    const selected = variants.find((v) => v.isUserSelected);
    const userDefault = variants.find((v) => v.isUserDefault);
    const globalDefault = variants.find((v) => v.isGlobalDefault);
    const firstCompatible = variants.find((v) => v.isCompatible !== false);

    const target = requested ?? selected ?? userDefault ?? globalDefault ?? firstCompatible;
    if (target) {
      applyVariantState(gridApi, target.state);
      appliedRef.current = target.id;
      setInternalActiveId(target.id);
      onActiveVariantChange?.(target.id);
    }
  }, [activeId, gridApi, variants, onActiveVariantChange]);

  // ── Close manager on outside click ─────────────────────────────────
  const managerRef = useRef<HTMLDivElement>(null);
  const toggleRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!showManager) return;
    const handler = (e: MouseEvent) => {
      if (
        managerRef.current &&
        !managerRef.current.contains(e.target as Node) &&
        toggleRef.current &&
        !toggleRef.current.contains(e.target as Node)
      ) {
        setShowManager(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showManager]);

  // ── Handlers ───────────────────────────────────────────────────────

  const handleSelect = useCallback(
    async (variantId: string) => {
      const variant = variants.find((v) => v.id === variantId);
      if (!variant || !gridApi) return;
      const previousActiveId = activeId;
      const previousVariant = previousActiveId
        ? variants.find((item) => item.id === previousActiveId) ?? null
        : null;

      applyVariantState(gridApi, variant.state);
      appliedRef.current = variantId;
      setInternalActiveId(variantId);
      onActiveVariantChange?.(variantId);

      try {
        await updateVariantPreference({ variantId, isSelected: true, gridId });
      } catch {
        // Preference sync failed (e.g. 401) — keep variant applied locally.
        // updateVariantPreference already falls back to localStorage.
        dispatchVariantToast("warning", m.variantPreferenceUpdateFailedLabel ?? "Varyant tercihi sunucuya kaydedilemedi");
      }
    },
    [activeId, gridApi, gridId, m.variantPreferenceUpdateFailedLabel, onActiveVariantChange, variants],
  );

  const handleClear = useCallback(() => {
    setInternalActiveId(null);
    appliedRef.current = null;
    // Clear variant-specific filters and sort when deselecting
    if (gridApi) {
      gridApi.setFilterModel?.(null);
      gridApi.setAdvancedFilterModel?.(null as unknown as AdvancedFilterModel);
      gridApi.setGridOption?.("quickFilterText", "");
      const rowModelType = gridApi.getGridOption?.("rowModelType");
      if (rowModelType === "serverSide") {
        gridApi.refreshServerSide?.({ purge: true });
      }
    }
    onActiveVariantChange?.(null);
  }, [gridApi, onActiveVariantChange]);

  const handleSave = useCallback(
    async (variantId: string) => {
      if (!gridApi) return;
      setPendingAction(`save-${variantId}`);
      const state = collectGridState(gridApi);
      try {
        await updateGridVariant({
          id: variantId,
          state: state as Record<string, unknown>,
          schemaVersion: gridSchemaVersion,
        });
        await loadVariants();
      } catch {
        // silent
      } finally {
        setPendingAction(null);
      }
    },
    [gridApi, gridSchemaVersion, loadVariants],
  );

  const handleCreate = useCallback(async () => {
    if (!gridApi) return;
    setPendingAction("create");
    const state = collectGridState(gridApi);
    const name = newVariantName.trim() || (m.defaultVariantName ?? "Adsiz Varyant");
    try {
      const created = await createGridVariant({
        gridId,
        name,
        state: state as Record<string, unknown>,
        schemaVersion: gridSchemaVersion,
        isDefault: false,
        isGlobal: false,
        isGlobalDefault: false,
      });
      if (created && typeof created === "object" && "id" in created) {
        setInternalActiveId((created as { id: string }).id);
        onActiveVariantChange?.((created as { id: string }).id);
      }
      setNewVariantName("");
      await loadVariants();
    } catch {
      // silent
    } finally {
      setPendingAction(null);
    }
  }, [gridApi, gridId, gridSchemaVersion, newVariantName, m.defaultVariantName, onActiveVariantChange, loadVariants]);

  const handleDelete = useCallback(
    async (variantId: string) => {
      setPendingAction(`delete-${variantId}`);
      try {
        await deleteGridVariant(variantId);
        if (activeId === variantId) {
          setInternalActiveId(null);
          appliedRef.current = null;
          onActiveVariantChange?.(null);
        }
        setConfirmDeleteId(null);
        // Optimistic state update — don't rely on loadVariants which may read stale cache
        setVariants((prev) => prev.filter((v) => v.id !== variantId));
      } catch {
        // silent — variant may still be in localStorage if API and local delete both failed
      } finally {
        setPendingAction(null);
      }
    },
    [activeId, onActiveVariantChange],
  );

  const handleClone = useCallback(
    async (variantId: string) => {
      setPendingAction(`clone-${variantId}`);
      try {
        await cloneGridVariant({ variantId });
        await loadVariants();
      } catch {
        // silent
      } finally {
        setPendingAction(null);
      }
    },
    [loadVariants],
  );

  const handleSetDefault = useCallback(
    async (variantId: string, isDefault: boolean) => {
      setPendingAction(`default-${variantId}`);
      try {
        await updateVariantPreference({ variantId, isDefault, gridId });
        await loadVariants();
      } catch {
        // silent
      } finally {
        setPendingAction(null);
      }
    },
    [loadVariants],
  );

  const handlePromoteToGlobal = useCallback(
    async (variantId: string) => {
      setPendingAction(`promote-${variantId}`);
      try {
        await updateGridVariant({ id: variantId, isGlobal: true });
        await loadVariants();
      } catch {
        // silent
      } finally {
        setPendingAction(null);
      }
    },
    [loadVariants],
  );

  const handleDemoteToPersonal = useCallback(
    async (variantId: string) => {
      setPendingAction(`demote-${variantId}`);
      try {
        await updateGridVariant({ id: variantId, isGlobal: false, isGlobalDefault: false });
        await loadVariants();
      } catch {
        // silent
      } finally {
        setPendingAction(null);
      }
    },
    [loadVariants],
  );

  const handleSetGlobalDefault = useCallback(
    async (variantId: string, isGlobalDefault: boolean) => {
      setPendingAction(`gdefault-${variantId}`);
      try {
        await updateGridVariant({ id: variantId, isGlobalDefault });
        await loadVariants();
      } catch {
        // silent
      } finally {
        setPendingAction(null);
      }
    },
    [loadVariants],
  );

  const handleRename = useCallback(
    async (variantId: string) => {
      const trimmed = renameValue.trim();
      if (!trimmed) {
        setRenamingVariantId(null);
        return;
      }
      setPendingAction(`rename-${variantId}`);
      try {
        await updateGridVariant({ id: variantId, name: trimmed });
        await loadVariants();
      } catch {
        // silent
      } finally {
        setRenamingVariantId(null);
        setPendingAction(null);
      }
    },
    [renameValue, loadVariants],
  );

  // ── Badge renderer ─────────────────────────────────────────────────

  const renderBadges = (v: GridVariant) => {
    const badges: React.ReactNode[] = [];

    if (v.id === activeId) {
      badges.push(
        <span key="sel" className="rounded-xs bg-action-primary/15 px-1 py-0.5 text-[10px] font-medium text-action-primary">
          {m.selectedTagLabel ?? "Secili"}
        </span>,
      );
    }
    if (v.isUserDefault) {
      badges.push(
        <span key="ud" className="rounded-xs bg-state-warning-bg px-1 py-0.5 text-[10px] font-medium text-state-warning-text">
          {m.personalDefaultTagLabel ?? "Varsayilan"}
        </span>,
      );
    }
    if (v.isGlobal && v.isGlobalDefault) {
      badges.push(
        <span key="gd" className="rounded-xs bg-state-success-bg px-1 py-0.5 text-[10px] font-medium text-state-success-text">
          {m.globalPublicDefaultTagLabel ?? "G. Varsayilan"}
        </span>,
      );
    }
    if (v.isCompatible === false) {
      badges.push(
        <span key="ic" className="rounded-xs bg-state-danger-bg px-1 py-0.5 text-[10px] font-medium text-state-danger-text">
          {m.incompatibleTagLabel ?? "Uyumsuz"}
        </span>,
      );
    }

    return badges.length > 0 ? <div className="flex items-center gap-1">{badges}</div> : null;
  };

  // ── Single variant row (accordion item) ────────────────────────────

  const renderVariantRow = (v: GridVariant, index: number) => {
    const itemState = accordion.getItemState(v.id);
    const triggerProps = itemState.getTriggerProps(index);
    const panelProps = itemState.getPanelProps();
    const isActive = v.id === activeId;
    const isBusy = pendingAction?.includes(v.id) ?? false;
    const isPersonal = !v.isGlobal;

    return (
      <div
        key={v.id}
        className={cn(
          "rounded-md border transition-colors",
          isActive
            ? "border-action-primary/30 bg-action-primary/5"
            : "border-transparent hover:bg-surface-muted",
        )}
      >
        {/* Collapsed row — h-8 compact */}
        <div className="flex h-8 items-center gap-1.5 px-2">
          {/* Select on name click */}
          <button
            type="button"
            className="min-w-0 flex-1 truncate text-left text-xs font-medium text-text-primary"
            onClick={() => handleSelect(v.id)}
            title={v.name}
          >
            {renamingVariantId === v.id ? (
              <input
                type="text"
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleRename(v.id);
                  if (e.key === "Escape") setRenamingVariantId(null);
                  e.stopPropagation();
                }}
                onBlur={() => handleRename(v.id)}
                onClick={(e) => e.stopPropagation()}
                onKeyUp={(e) => e.stopPropagation()}
                onInput={(e) => e.stopPropagation()}
                className="h-5 w-full rounded-xs border border-border-default bg-surface-default px-1 text-xs outline-hidden"
                autoFocus
              />
            ) : (
              v.name
            )}
          </button>

          {/* Badges */}
          {renderBadges(v)}

          {/* Accordion trigger (chevron) */}
          <button
            type="button"
            {...triggerProps}
            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-xs text-text-disabled hover:text-text-primary"
          >
            <ChevronIcon expanded={itemState.isExpanded} />
          </button>
        </div>

        {/* Expanded detail panel — accordion content */}
        <div {...panelProps} className={cn("overflow-hidden", !itemState.isExpanded && "hidden")}>
          {confirmDeleteId === v.id ? (
            /* Delete confirmation */
            <div className="flex items-center gap-2 border-t border-border-subtle/50 px-2 py-2">
              <span className="flex-1 text-xs text-state-error-text">
                {m.deleteVariantConfirmationLabel ?? "Silmek istediginize emin misiniz?"}
              </span>
              <button
                type="button"
                className="rounded-xs bg-state-error-text px-2 py-0.5 text-[10px] font-medium text-text-inverse hover:brightness-110 disabled:opacity-50"
                onClick={() => handleDelete(v.id)}
                disabled={isBusy}
              >
                {m.menuDeleteLabel ?? "Sil"}
              </button>
              <button
                type="button"
                className="rounded-xs bg-surface-muted px-2 py-0.5 text-[10px] font-medium text-text-secondary hover:bg-surface-raised"
                onClick={() => setConfirmDeleteId(null)}
              >
                {m.cancelLabel ?? "Iptal"}
              </button>
            </div>
          ) : (
            /* Action buttons */
            <div className="flex flex-wrap items-center gap-1 border-t border-border-subtle/50 px-2 py-2">
              {/* Save current state */}
              {isActive && (
                <ActionBtn
                  onClick={() => handleSave(v.id)}
                  disabled={isBusy}
                  title={m.saveCurrentLayoutTitle ?? "Mevcut durumu kaydet"}
                >
                  {m.saveCurrentStateLabel ?? "Kaydet"}
                </ActionBtn>
              )}

              {/* Set/Unset default */}
              {v.isUserDefault ? (
                <ActionBtn
                  onClick={() => handleSetDefault(v.id, false)}
                  disabled={isBusy}
                  variant="active"
                >
                  {m.menuUnsetDefaultLabel ?? "Varsayilani Kaldir"}
                </ActionBtn>
              ) : (
                <ActionBtn
                  onClick={() => handleSetDefault(v.id, true)}
                  disabled={isBusy}
                >
                  {m.menuSetDefaultLabel ?? "Varsayilan Yap"}
                </ActionBtn>
              )}

              {/* Personal-specific actions */}
              {isPersonal && (
                <>
                  {canPromoteToGlobal && (
                    <ActionBtn
                      onClick={() => handlePromoteToGlobal(v.id)}
                      disabled={isBusy}
                      title={m.moveToGlobalTitle ?? "Paylasilan varyantlara tasi"}
                    >
                      {m.menuMoveToGlobalLabel ?? "Globale Tasi"}
                    </ActionBtn>
                  )}
                  <ActionBtn
                    onClick={() => {
                      setRenamingVariantId(v.id);
                      setRenameValue(v.name);
                    }}
                    disabled={isBusy}
                  >
                    {m.menuRenameLabel ?? "Yeniden Adlandir"}
                  </ActionBtn>
                  <ActionBtn
                    onClick={() => setConfirmDeleteId(v.id)}
                    disabled={isBusy}
                    variant="danger"
                  >
                    {m.menuDeleteLabel ?? "Sil"}
                  </ActionBtn>
                </>
              )}

              {/* Global-specific actions */}
              {!isPersonal && (
                <>
                  {/* Clone to personal — everyone can do this */}
                  <ActionBtn
                    onClick={() => handleClone(v.id)}
                    disabled={isBusy}
                  >
                    Kopya Al
                  </ActionBtn>

                  {/* Set/Unset global default — requires promote permission */}
                  {canPromoteToGlobal && (
                    v.isGlobalDefault ? (
                      <ActionBtn
                        onClick={() => handleSetGlobalDefault(v.id, false)}
                        disabled={isBusy}
                        variant="active"
                      >
                        {m.menuUnsetGlobalDefaultLabel ?? "G. Varsayilani Kaldir"}
                      </ActionBtn>
                    ) : (
                      <ActionBtn
                        onClick={() => handleSetGlobalDefault(v.id, true)}
                        disabled={isBusy}
                      >
                        {m.menuSetGlobalDefaultLabel ?? "G. Varsayilan Yap"}
                      </ActionBtn>
                    )
                  )}

                  {/* Demote to personal */}
                  {canDemoteToPersonal && (
                    <ActionBtn
                      onClick={() => handleDemoteToPersonal(v.id)}
                      disabled={isBusy}
                      title={m.moveToPersonalTitle ?? "Kisisele tasi"}
                    >
                      {m.menuMoveToPersonalLabel ?? "Kisisele Tasi"}
                    </ActionBtn>
                  )}

                  {/* Rename — only with permission */}
                  {canDemoteToPersonal && (
                    <ActionBtn
                      onClick={() => {
                        setRenamingVariantId(v.id);
                        setRenameValue(v.name);
                      }}
                      disabled={isBusy}
                    >
                      {m.menuRenameLabel ?? "Yeniden Adlandir"}
                    </ActionBtn>
                  )}

                  {/* Delete global — requires canDeleteGlobal */}
                  {canDeleteGlobal && (
                    <ActionBtn
                      onClick={() => setConfirmDeleteId(v.id)}
                      disabled={isBusy}
                      variant="danger"
                    >
                      {m.menuDeleteLabel ?? "Sil"}
                    </ActionBtn>
                  )}
                </>
              )}
            </div>
          )}
        </div>
      </div>
    );
  };

  // ── Render ─────────────────────────────────────────────────────────

  return (
    <div className="relative">
      {/* Variant selector dropdown (inline in toolbar) */}
      <div className={`flex items-center gap-2 ${accessStyles(accessState.state)}`} data-component="variant-selector" data-access-state={accessState.state} title={accessReason}>
        <select
          value={activeId ?? ""}
          onChange={(e) => {
            const val = e.target.value;
            if (val) handleSelect(val);
            else handleClear();
          }}
          disabled={loading || variants.length === 0}
          className="h-8 min-w-[160px] rounded-md border border-border-default bg-surface-default px-2 text-sm text-text-primary"
          aria-label={m.variantLabel ?? "Grid variant"}
        >
          <option value="">{m.variantPlaceholder ?? "\u2014 Variant \u2014"}</option>
          {personalVariants.length > 0 && (
            <optgroup label={m.personalVariantsTitle ?? "Kisisel"}>
              {personalVariants.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                  {v.isUserDefault ? " \u2605" : ""}
                </option>
              ))}
            </optgroup>
          )}
          {globalVariants.length > 0 && (
            <optgroup label={m.globalVariantsTitle ?? "Paylasilan"}>
              {globalVariants.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name}
                  {v.isGlobalDefault ? " \u2605" : ""}
                </option>
              ))}
            </optgroup>
          )}
        </select>

        {activeId && (
          <button
            type="button"
            className="h-8 rounded-md bg-surface-muted px-2 text-xs font-medium text-text-secondary hover:bg-surface-raised"
            onClick={() => handleSave(activeId)}
            disabled={pendingAction === `save-${activeId}`}
            title={m.saveTitle ?? "Save current state to variant"}
          >
            <IconSave size={14} />
          </button>
        )}

        <button
          ref={toggleRef}
          type="button"
          className="h-8 rounded-md bg-surface-muted px-2 text-xs font-medium text-text-secondary hover:bg-surface-raised"
          onClick={() => setShowManager(!showManager)}
          title={m.variantModalTitle ?? "Manage variants"}
          aria-label={m.variantModalTitle ?? "Varyantları yönet"}
        >
          <IconSettings size={14} />
        </button>
      </div>

      {/* Variant manager panel — portal to body to avoid overflow clipping */}
      {showManager && typeof document !== "undefined" && createPortal(
        <div
          ref={managerRef}
          className="fixed z-[9999] w-96 max-h-[70vh] overflow-y-auto rounded-lg border border-border-default bg-surface-default shadow-lg"
          data-component="variant-manager"
          onKeyDown={(e) => e.stopPropagation()}
          onKeyUp={(e) => e.stopPropagation()}
          style={{
            top: toggleRef.current
              ? toggleRef.current.getBoundingClientRect().bottom + 4
              : 200,
            left: toggleRef.current
              ? Math.min(
                  toggleRef.current.getBoundingClientRect().right - 384, // 384 = w-96
                  window.innerWidth - 400,
                )
              : 100,
          }}
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-border-subtle px-3 py-2">
            <h3 className="text-sm font-semibold text-text-primary">
              {m.variantModalTitle ?? "Varyantlar"}
            </h3>
            <button
              type="button"
              className="flex h-5 w-5 items-center justify-center rounded-xs text-text-disabled hover:text-text-primary"
              onClick={() => setShowManager(false)}
              title={m.closeVariantManagerLabel ?? "Kapat"}
            >
              <IconClose size={12} />
            </button>
          </div>

          {/* Create form — always creates personal */}
          <div className="flex items-center gap-2 border-b border-border-subtle px-3 py-2">
            <input
              type="text"
              value={newVariantName}
              onChange={(e) => setNewVariantName(e.target.value)}
              placeholder={m.variantNamePlaceholder ?? "Varyant adi"}
              className="h-7 flex-1 rounded-xs border border-border-default bg-surface-default px-2 text-xs outline-hidden focus:border-action-primary"
              onKeyDown={(e) => {
                e.stopPropagation();
                if (e.key === "Enter") handleCreate();
              }}
              onKeyUp={(e) => e.stopPropagation()}
              onInput={(e) => e.stopPropagation()}
            />
            <button
              type="button"
              className="h-7 rounded-xs bg-action-primary px-3 text-xs font-medium text-text-inverse hover:brightness-110 disabled:opacity-50"
              onClick={handleCreate}
              disabled={pendingAction === "create"}
            >
              {m.variantNewButtonLabel ?? "Olustur"}
            </button>
          </div>

          {/* Variant sections */}
          <div className="max-h-80 overflow-y-auto">
            {/* Personal section */}
            <div className="px-3 py-2">
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-disabled">
                {m.personalVariantsTitle ?? "Kisisel"}
              </div>
              {personalVariants.length === 0 && !loading ? (
                <p className="py-1 text-xs text-text-disabled">
                  {m.personalVariantsEmptyLabel ?? "Kisisel varyant yok"}
                </p>
              ) : (
                <div className="flex flex-col gap-0.5">
                  {personalVariants.map((v, i) => renderVariantRow(v, i))}
                </div>
              )}
            </div>

            {/* Divider */}
            <div className="mx-3 border-t border-border-subtle" />

            {/* Global section */}
            <div className="px-3 py-2">
              <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-text-disabled">
                {m.globalVariantsTitle ?? "Paylasilan"}
              </div>
              {globalVariants.length === 0 && !loading ? (
                <p className="py-1 text-xs text-text-disabled">
                  {m.globalVariantsEmptyLabel ?? "Paylasilan varyant yok"}
                </p>
              ) : (
                <div className="flex flex-col gap-0.5">
                  {globalVariants.map((v, i) => renderVariantRow(v, personalVariants.length + i))}
                </div>
              )}
            </div>
          </div>
        </div>,
        document.body,
      )}
    </div>
  );
};

VariantIntegration.displayName = "VariantIntegration";

/* ------------------------------------------------------------------ */
/*  Action button (tiny, reused in accordion detail)                   */
/* ------------------------------------------------------------------ */

function ActionBtn({
  children,
  onClick,
  disabled,
  variant,
  title,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  variant?: "danger" | "active";
  title?: string;
}) {
  return (
    <button
      type="button"
      className={cn(
        "rounded-xs px-1.5 py-0.5 text-[10px] font-medium transition-colors disabled:opacity-50",
        variant === "danger"
          ? "text-state-error-text hover:bg-state-danger-bg"
          : variant === "active"
            ? "bg-state-warning-bg text-state-warning-text hover:bg-[var(--state-warning-bg-hover)]"
            : "text-text-secondary hover:bg-surface-muted",
      )}
      onClick={onClick}
      disabled={disabled}
      title={title}
    >
      {children}
    </button>
  );
}

export default VariantIntegration;
