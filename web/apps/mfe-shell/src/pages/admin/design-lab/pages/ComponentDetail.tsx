import React, { useMemo, useState, _useCallback } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import {
  Copy,
  Check,
  Code2,
  Eye,
  ChevronRight,
  Layers,
  Gamepad2,
  FileCode2,
  BookOpen,
  ShieldCheck,
  ArrowRight,
  Globe,
  History,
  BookOpenCheck,
  Paintbrush,
  Palette,
  Clock,
} from "lucide-react";
import { Text, IconButton } from "@mfe/design-system";
import {
  LibraryPreviewPanel,
  LibraryCodeBlock,
  LibraryDocsSection,
  LibraryDetailLabel,
  CodeBlock,
} from "../../../../../../../packages/design-system/src/catalog/design-lab-internals";
import { useDesignLab } from "../DesignLabProvider";
import { isDesignLabUrlTokenFlexibleMatch } from "../designLabUrlMatch";
import {
  ComponentPlayground,
  PlaygroundPreview,
  PreviewToolbar,
  PreviewThemeWrapper,
  StatePreviewWrapper,
  ViewportFrame,
} from "../playground";
import type { PreviewAppearance, PreviewViewport } from "../playground";
import { PropsTableV2 } from "../api/PropsTableV2";
import { ExamplesGallery } from "../examples";
import { GuideTab } from "../docs";
import { TokensTab } from "../tabs/TokensTab";
import { PropsDepsGraph } from "../api/PropsDepsGraph";
import { ViewSourceModal } from "../source/ViewSourceModal";
import { SuggestedPatterns } from "../ai/SuggestedPatterns";
import { StyleTab } from "../tabs/StyleTab";
import { STATE_PROP_MAP } from "../shared/statePropMap";
import { EnterpriseReadyChecklist } from "../components/EnterpriseReadyChecklist";

/* ------------------------------------------------------------------ */
/*  ComponentDetail — World-class component documentation page         */
/*                                                                     */
/*  Tabs: Overview · Playground · API · Examples · Quality              */
/*  Surpasses Ant Design / MUI / Shadcn with:                          */
/*    - Auto-generated variant galleries                               */
/*    - Size scale comparison                                          */
/*    - State demonstrations                                           */
/*    - Live preview + code toggle on every section                    */
/*    - A11y scorecard                                                 */
/* ------------------------------------------------------------------ */

type DetailTab = "overview" | "playground" | "api" | "examples" | "guide" | "tokens" | "style" | "quality" | "changelog";

const DETAIL_TAB_META: Array<{ id: DetailTab; icon: React.ReactNode }> = [
  { id: "overview", icon: <Layers className="h-3.5 w-3.5" /> },
  { id: "playground", icon: <Gamepad2 className="h-3.5 w-3.5" /> },
  { id: "api", icon: <FileCode2 className="h-3.5 w-3.5" /> },
  { id: "examples", icon: <BookOpen className="h-3.5 w-3.5" /> },
  { id: "guide", icon: <BookOpenCheck className="h-3.5 w-3.5" /> },
  { id: "tokens", icon: <Paintbrush className="h-3.5 w-3.5" /> },
  { id: "style", icon: <Palette className="h-3.5 w-3.5" /> },
  { id: "quality", icon: <ShieldCheck className="h-3.5 w-3.5" /> },
  { id: "changelog", icon: <History className="h-3.5 w-3.5" /> },
];

/* ---- Utility: parse "variant: primary | secondary | ghost" → {axis, values} ---- */

type ParsedAxis = { axis: string; values: string[] };

function parseVariantAxes(axes: string[]): ParsedAxis[] {
  return axes
    .map((raw) => {
      const colonIdx = raw.indexOf(":");
      if (colonIdx === -1) return null;
      const axis = raw.slice(0, colonIdx).trim();
      const values = raw
        .slice(colonIdx + 1)
        .split("|")
        .map((v) => v.trim())
        .filter(Boolean);
      if (!axis || values.length === 0) return null;
      return { axis, values };
    })
    .filter((x): x is ParsedAxis => x !== null);
}

/* ---- Complex / wide-layout components that need scaled-down variant previews ---- */

const COMPLEX_PREVIEW_COMPONENTS = new Set([
  "PageLayout", "EntityGridTemplate", "AgGridServer", "DetailDrawer", "FormDrawer",
  "NavigationRail", "DetailSectionTabs", "SearchFilterListing",
  "NotificationDrawer", "CitationPanel", "CommandPalette",
  "ApprovalReview", "AIGuidedAuthoring", "DetailSummary",
  "TourCoachmarks", "NotificationPanel", "ReportFilterPanel",
  "FilterBar", "PageHeader", "SummaryStrip", "EntitySummaryBlock",
  "AIActionAuditTimeline", "ApprovalCheckpoint", "PromptComposer",
  "RecommendationCard", "ThemePresetCompare", "ThemePresetGallery",
  "MasterDetail", "MenuBar", "TreeTable", "TableSimple",
  "CrudTemplate", "DashboardTemplate", "DetailTemplate", "SettingsTemplate", "CommandWorkspace",
  "CRUD Template", "Dashboard Template", "Detail Template", "Settings Template", "Command Workspace",
  "NavigationMenu", "AppHeader", "CommandHeader", "ActionHeader", "DesktopMenubar",
  "Navigation Menu", "App Header", "Search / Command Header", "Action Header", "Action Bar", "Desktop Menubar",
]);

/* ---- Utility: generate JSX code snippet ---- */

function generateCodeSnippet(
  componentName: string,
  props: Record<string, unknown>,
  children?: string,
): string {
  const entries = Object.entries(props).filter(
    ([k]) => k !== "children",
  );

  const propsStr = entries
    .map(([k, v]) => {
      if (typeof v === "boolean") return v ? k : `${k}={false}`;
      if (typeof v === "number") return `${k}={${v}}`;
      if (typeof v === "string") return `${k}="${v}"`;
      return `${k}={${JSON.stringify(v)}}`;
    })
    .join(" ");

  const openTag = propsStr
    ? `<${componentName} ${propsStr}`
    : `<${componentName}`;

  if (children) {
    return `${openTag}>\n  ${children}\n</${componentName}>`;
  }
  return `${openTag} />`;
}

/* ================================================================== */
/*  Main Component                                                     */
/* ================================================================== */

export default function ComponentDetail() {
  const { groupId, itemId } = useParams<{
    groupId: string;
    itemId: string;
  }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { indexItemMap, apiItemMap, t } = useDesignLab();

  /* Detect which layer we're on from the URL path */
  const layer = useMemo(() => {
    const path = location.pathname;
    if (path.includes("/primitives/")) return "primitives";
    if (path.includes("/advanced/")) return "advanced";
    return "components";
  }, [location.pathname]);

  const [activeTab, setActiveTab] = useState<DetailTab>("overview");
  const [copied, setCopied] = useState(false);
  const [showSource, setShowSource] = useState(false);

  // Resolve itemId from URL — the URL may contain URL-encoded names, PascalCase
  // keys, or partial tokens. We first try a direct lookup, then fall back to
  // flexible matching (handles names with spaces / slashes like "Search / Command Header").
  const resolvedItemName = useMemo(() => {
    if (!itemId) return undefined;
    // Direct match
    if (indexItemMap.has(itemId)) return itemId;
    // Flexible match: iterate the map to find a match
    for (const key of indexItemMap.keys()) {
      if (isDesignLabUrlTokenFlexibleMatch(key, itemId)) return key;
    }
    // Try decoding the URL (handles %20 etc.) and ~ → / restoration
    try {
      const decoded = decodeURIComponent(itemId).replace(/~/g, ' / ');
      if (indexItemMap.has(decoded)) return decoded;
      for (const key of indexItemMap.keys()) {
        if (isDesignLabUrlTokenFlexibleMatch(key, decoded)) return key;
      }
      // Also try without ~ restoration (plain decode)
      const plainDecoded = decodeURIComponent(itemId);
      if (plainDecoded !== decoded) {
        if (indexItemMap.has(plainDecoded)) return plainDecoded;
        for (const key of indexItemMap.keys()) {
          if (isDesignLabUrlTokenFlexibleMatch(key, plainDecoded)) return key;
        }
      }
    } catch { /* noop */ }
    return undefined;
  }, [itemId, indexItemMap]);

  const indexItem = useMemo(
    () => (resolvedItemName ? indexItemMap.get(resolvedItemName) : undefined),
    [resolvedItemName, indexItemMap],
  );

  const apiItem = useMemo(
    () => (resolvedItemName ? apiItemMap.get(resolvedItemName) : undefined),
    [resolvedItemName, apiItemMap],
  );

  const handleCopyImport = async () => {
    if (!indexItem?.importStatement) return;
    try {
      await navigator.clipboard.writeText(indexItem.importStatement);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* noop */
    }
  };

  if (!indexItem) {
    return (
      <div className="rounded-2xl border border-border-subtle bg-surface-default p-8 text-center">
        <Text variant="secondary">
          {t("designlab.detail.notFound")}
        </Text>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {/* ── Breadcrumb ── */}
      <nav className="flex items-center gap-1.5 text-xs text-text-secondary">
        <button
          type="button"
          onClick={() => navigate("/admin/design-lab")}
          className="rounded-md px-1.5 py-0.5 transition-colors hover:bg-surface-muted hover:text-text-primary"
        >
          {t("designlab.breadcrumb.library")}
        </button>
        <ChevronRight className="h-3 w-3 opacity-40" />
        <button
          type="button"
          onClick={() => navigate(`/admin/design-lab/${layer}`)}
          className="rounded-md px-1.5 py-0.5 transition-colors hover:bg-surface-muted hover:text-text-primary"
        >
          {t(`designlab.sidebar.title.${layer}`)}
        </button>
        {groupId && (
          <>
            <ChevronRight className="h-3 w-3 opacity-40" />
            <button
              type="button"
              onClick={() =>
                navigate(`/admin/design-lab/${layer}/${groupId}`)
              }
              className="rounded-md px-1.5 py-0.5 transition-colors hover:bg-surface-muted hover:text-text-primary"
            >
              {groupId}
            </button>
          </>
        )}
        <ChevronRight className="h-3 w-3 opacity-40" />
        <span className="rounded-md bg-surface-muted px-2 py-0.5 font-medium text-text-primary">
          {itemId}
        </span>
      </nav>

      {/* ── Hero header ── */}
      <div className="relative overflow-hidden rounded-2xl border border-border-subtle bg-linear-to-br from-surface-default via-surface-default to-surface-canvas p-6 sm:p-8">
        {/* Decorative dots */}
        <div
          className="pointer-events-none absolute inset-0 opacity-[0.02]"
          style={{
            backgroundImage: "radial-gradient(circle, currentColor 1px, transparent 1px)",
            backgroundSize: "20px 20px",
          }}
        />

        <div className="relative flex items-start justify-between gap-4">
          <div className="min-w-0 flex-1">
            <Text
              as="div"
              className="text-2xl font-extrabold tracking-tight text-text-primary sm:text-3xl"
            >
              {indexItem.name}
            </Text>
            <div className="mt-2 flex items-center gap-2">
              <Text
                variant="secondary"
                className="max-w-2xl text-sm leading-relaxed"
              >
                {indexItem.description}
              </Text>
              <button
                type="button"
                onClick={() => setShowSource(true)}
                className="shrink-0 flex items-center gap-1 rounded-lg border border-border-subtle px-2 py-1 text-[11px] font-medium text-text-secondary hover:text-text-primary hover:bg-surface-muted transition"
              >
                <Code2 className="h-3 w-3" /> View Source
              </button>
            </div>

            {/* Badges */}
            <div className="mt-4 flex flex-wrap items-center gap-2">
              <span
                className={[
                  "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold",
                  indexItem.lifecycle === "stable"
                    ? "bg-state-success-bg text-state-success-text"
                    : indexItem.lifecycle === "beta"
                      ? "bg-state-warning-bg text-state-warning-text"
                      : "bg-state-info-bg text-state-info-text",
                ].join(" ")}
              >
                <span
                  className={[
                    "h-1.5 w-1.5 rounded-full",
                    indexItem.lifecycle === "stable"
                      ? "bg-state-success-text"
                      : indexItem.lifecycle === "beta"
                        ? "bg-state-warning-text"
                        : "bg-state-info-text",
                  ].join(" ")}
                />
                {indexItem.lifecycle}
              </span>
              {indexItem.maturity && (
                <span
                  className={[
                    "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold",
                    indexItem.maturity === "enterprise"
                      ? "bg-action-primary/10 text-action-primary"
                      : indexItem.maturity === "stable"
                        ? "bg-state-success-text/10 text-state-success-text"
                        : indexItem.maturity === "beta"
                          ? "bg-state-warning-text/10 text-state-warning-text"
                          : "bg-state-info-text/10 text-state-info-text",
                  ].join(" ")}
                >
                  {indexItem.maturity === "enterprise" ? "🏢" : indexItem.maturity === "stable" ? "✅" : indexItem.maturity === "beta" ? "🔶" : "🧪"}
                  {" "}{indexItem.maturity}
                </span>
              )}
              {indexItem.roadmapWaveId && (
                <span className="rounded-full border border-border-subtle bg-surface-canvas px-2.5 py-0.5 text-xs font-medium text-text-secondary">
                  {indexItem.roadmapWaveId}
                </span>
              )}
              {indexItem.tags?.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-border-subtle bg-surface-canvas px-2.5 py-0.5 text-xs font-medium text-text-secondary"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Import statement — modern code bar */}
        {indexItem.importStatement && (
          <div className="relative mt-5 flex items-center gap-2 rounded-xl border border-border-subtle bg-surface-canvas/80 px-4 py-2.5 backdrop-blur-xs">
            <div className="mr-2 rounded-md bg-surface-muted px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-text-secondary">
              import
            </div>
            <code className="flex-1 overflow-x-auto font-mono text-xs text-text-primary">
              {indexItem.importStatement}
            </code>
            <IconButton
              icon={
                copied ? (
                  <Check className="h-3.5 w-3.5 text-state-success-text" />
                ) : (
                  <Copy className="h-3.5 w-3.5" />
                )
              }
              label={t("designlab.detail.copyImport")}
              size="sm"
              variant="ghost"
              onClick={handleCopyImport}
            />
          </div>
        )}
      </div>

      {/* ── Tab navigation — Pill style ── */}
      <div className="rounded-xl border border-border-subtle bg-surface-default p-1.5">
        <div className="flex gap-1">
          {DETAIL_TAB_META.map(({ id, icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setActiveTab(id)}
              className={[
                "flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-200",
                activeTab === id
                  ? "bg-action-primary text-text-inverse shadow-xs"
                  : "text-text-secondary hover:bg-surface-muted hover:text-text-primary",
              ].join(" ")}
            >
              {icon}
              <span className="hidden sm:inline">
                {t(`designlab.detail.tab.${id}`)}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* ── Tab content ── */}
      <div className="min-h-[400px]">
        {activeTab === "overview" && (
          <OverviewTab indexItem={indexItem} apiItem={apiItem} />
        )}
        {activeTab === "playground" && (
          <ComponentPlayground
            componentName={indexItem.name}
            apiItem={apiItem}
            importStatement={indexItem.importStatement}
          />
        )}
        {activeTab === "api" && <ApiTab apiItem={apiItem} componentName={indexItem.name} />}
        {activeTab === "examples" && (
          <div className="flex flex-col gap-8">
            <ExamplesGallery
              componentName={indexItem.name}
              fallbackContent={
                <ComponentExamplesTab
                  componentName={indexItem.name}
                  apiItem={apiItem}
                  importStatement={indexItem.importStatement}
                />
              }
            />
            <SuggestedPatterns
              componentName={indexItem.name}
              componentProps={apiItem?.props?.map((p: { name: string }) => p.name) ?? []}
            />
          </div>
        )}
        {activeTab === "guide" && (
          <GuideTab componentName={indexItem.name} />
        )}
        {activeTab === "tokens" && (
          <TokensTab componentName={indexItem.name} />
        )}
        {activeTab === "style" && (
          <StyleTab componentName={indexItem.name} />
        )}
        {activeTab === "quality" && (
          <QualityTab indexItem={indexItem} apiItem={apiItem} />
        )}
        {activeTab === "changelog" && (
          <ChangelogTab componentName={indexItem.name} />
        )}
      </div>

      {/* View Source Modal */}
      <ViewSourceModal
        isOpen={showSource}
        onClose={() => setShowSource(false)}
        componentName={indexItem.name}
        importStatement={indexItem.importStatement}
      />
    </div>
  );
}

/* ================================================================== */
/*  Type helpers for tab props                                         */
/* ================================================================== */

type IndexItem = NonNullable<
  ReturnType<typeof useDesignLab>["indexItemMap"] extends Map<string, infer V>
    ? V
    : never
>;
type ApiItem =
  ReturnType<typeof useDesignLab>["apiItemMap"] extends Map<string, infer V>
    ? V | undefined
    : never;

/* ================================================================== */
/*  OverviewTab — Hero + Variant Gallery + Size + States + Meta        */
/* ================================================================== */

function OverviewTab({
  indexItem,
  apiItem,
}: {
  indexItem: IndexItem;
  apiItem: ApiItem;
}) {
  const { t } = useDesignLab();
  const parsedAxes = useMemo(
    () => parseVariantAxes(apiItem?.variantAxes ?? []),
    [apiItem?.variantAxes],
  );

  const sizeAxis = parsedAxes.find((a) => a.axis === "size");
  const variantAxes = parsedAxes.filter((a) => a.axis !== "size");

  return (
    <div className="flex flex-col gap-8">
      {/* 1. Component Hero Preview */}
      <HeroPreview componentName={indexItem.name} />

      {/* 2. Variant Gallery — one section per axis */}
      {variantAxes.map((axis) => (
        <VariantGallerySection
          key={axis.axis}
          componentName={indexItem.name}
          axis={axis}
        />
      ))}

      {/* 3. Size Scale */}
      {sizeAxis && (
        <SizeScaleSection componentName={indexItem.name} sizes={sizeAxis.values} />
      )}

      {/* 4. State Demonstrations — only preview-mappable states */}
      {apiItem && getEffectivePreviewStates(apiItem).length > 0 && (
        <StateDemoSection
          componentName={indexItem.name}
          states={getEffectivePreviewStates(apiItem)}
          componentProps={new Set((apiItem.props ?? []).map((p) => p.name))}
          isExplicitPreviewStates={!!(apiItem?.previewStates && apiItem.previewStates.length > 0)}
        />
      )}

      {/* 5. Metadata Cards — Modern grid */}
      <div className="grid gap-4 lg:grid-cols-2">
        {apiItem && (apiItem.props ?? []).length > 0 && (
          <div className="group rounded-2xl border border-border-subtle bg-surface-default p-5 transition-all duration-300 hover:border-border-default hover:shadow-xs">
            <div className="mb-4 flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-state-info-bg">
                <FileCode2 className="h-3.5 w-3.5 text-state-info-text" />
              </div>
              <Text as="div" className="text-sm font-semibold text-text-primary">
                {t("designlab.detail.overview.keyProps")}
              </Text>
              <span className="ml-auto rounded-full bg-surface-muted px-2 py-0.5 text-[10px] font-semibold tabular-nums text-text-secondary">
                {(apiItem.props ?? []).length}
              </span>
            </div>
            <div className="flex flex-col gap-1.5">
              {(apiItem.props ?? []).slice(0, 8).map((prop) => (
                <div
                  key={prop.name}
                  className="flex items-baseline justify-between gap-4 rounded-lg px-2 py-1.5 transition-colors hover:bg-surface-canvas"
                >
                  <code className="text-xs font-semibold text-text-primary">
                    {prop.name}
                  </code>
                  <code className="truncate text-[11px] text-state-info-text/70">
                    {prop.type}
                  </code>
                </div>
              ))}
              {(apiItem.props ?? []).length > 8 && (
                <Text variant="secondary" className="px-2 text-xs">
                  +{(apiItem.props ?? []).length - 8} more
                </Text>
              )}
            </div>
          </div>
        )}

        {apiItem && (apiItem.variantAxes ?? []).length > 0 && (
          <div className="group rounded-2xl border border-border-subtle bg-surface-default p-5 transition-all duration-300 hover:border-border-default hover:shadow-xs">
            <div className="mb-4 flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-action-primary/10">
                <Layers className="h-3.5 w-3.5 text-action-primary" />
              </div>
              <Text as="div" className="text-sm font-semibold text-text-primary">
                {t("designlab.detail.overview.variants")}
              </Text>
            </div>
            <div className="flex flex-wrap gap-2">
              {(apiItem.variantAxes ?? []).map((axis) => (
                <span
                  key={axis}
                  className="rounded-lg border border-border-subtle bg-surface-canvas px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:border-border-default hover:text-text-primary"
                >
                  {axis}
                </span>
              ))}
            </div>
          </div>
        )}

        {apiItem && (getEffectivePreviewStates(apiItem).length > 0 || getEffectiveBehaviorModel(apiItem).length > 0) && (
          <div className="group rounded-2xl border border-border-subtle bg-surface-default p-5 transition-all duration-300 hover:border-border-default hover:shadow-xs">
            <div className="mb-4 flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-state-warning-bg">
                <Gamepad2 className="h-3.5 w-3.5 text-state-warning-text" />
              </div>
              <Text as="div" className="text-sm font-semibold text-text-primary">
                {t("designlab.detail.overview.stateModel")}
              </Text>
            </div>
            {/* Preview states — these produce live visual demos */}
            {getEffectivePreviewStates(apiItem).length > 0 && (
              <div className="mb-3">
                <Text variant="secondary" className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider">
                  Preview States
                </Text>
                <div className="flex flex-wrap gap-2">
                  {getEffectivePreviewStates(apiItem).map((state) => (
                    <span
                      key={state}
                      className="rounded-lg border border-state-success-border bg-state-success-bg px-3 py-1.5 text-xs font-medium text-state-success-text transition-colors hover:border-state-success-border"
                    >
                      {state}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {/* Behavior model — descriptive, shown in docs only */}
            {getEffectiveBehaviorModel(apiItem).length > 0 && (
              <div>
                <Text variant="secondary" className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider">
                  Behavior Model
                </Text>
                <div className="flex flex-wrap gap-2">
                  {getEffectiveBehaviorModel(apiItem).map((behavior) => (
                    <span
                      key={behavior}
                      className="rounded-lg border border-border-subtle bg-surface-canvas px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:border-border-default hover:text-text-primary"
                    >
                      {behavior}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {(indexItem?.whereUsed ?? []).length > 0 && (
          <div className="group rounded-2xl border border-border-subtle bg-surface-default p-5 transition-all duration-300 hover:border-border-default hover:shadow-xs">
            <div className="mb-4 flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-state-success-bg">
                <Globe className="h-3.5 w-3.5 text-state-success-text" />
              </div>
              <Text as="div" className="text-sm font-semibold text-text-primary">
                {t("designlab.detail.overview.whereUsed")}
              </Text>
              <span className="ml-auto rounded-full bg-surface-muted px-2 py-0.5 text-[10px] font-semibold tabular-nums text-text-secondary">
                {(indexItem?.whereUsed ?? []).length}
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {(indexItem?.whereUsed ?? []).slice(0, 8).map((app) => (
                <span
                  key={app}
                  className="rounded-lg border border-border-subtle bg-surface-canvas px-3 py-1.5 text-xs font-medium text-text-secondary transition-colors hover:border-border-default hover:text-text-primary"
                >
                  {app}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ---- Hero Preview ---- */

function HeroPreview({ componentName }: { componentName: string }) {
  const [showCode, setShowCode] = useState(false);
  const [appearance, setAppearance] = useState<PreviewAppearance>("light");
  const [viewport, setViewport] = useState<PreviewViewport>("desktop");
  const code = generateCodeSnippet(componentName, {}, "Click me");

  return (
    <LibraryPreviewPanel title="Live Preview">
      <div className="relative">
        <div className="mb-3 flex items-center justify-between">
          <PreviewToolbar
            appearance={appearance}
            viewport={viewport}
            onAppearanceChange={setAppearance}
            onViewportChange={setViewport}
          />
          <button
            type="button"
            onClick={() => setShowCode(!showCode)}
            className="flex items-center gap-1.5 rounded-lg border border-border-subtle bg-surface-default/80 px-2.5 py-1.5 text-xs font-medium text-text-secondary backdrop-blur-xs transition hover:bg-surface-default hover:text-text-primary"
          >
            {showCode ? (
              <>
                <Eye className="h-3.5 w-3.5" /> Preview
              </>
            ) : (
              <>
                <Code2 className="h-3.5 w-3.5" /> Code
              </>
            )}
          </button>
        </div>

        {showCode ? (
          <div className="pt-2">
            <LibraryCodeBlock code={code} languageLabel="tsx" />
          </div>
        ) : (
          <PreviewThemeWrapper
            appearance={appearance}
            className="overflow-hidden rounded-2xl"
          >
            <ViewportFrame viewport={viewport}>
              <div className="flex min-h-[160px] items-center justify-center p-8">
                <PlaygroundPreview
                  componentName={componentName}
                  propValues={{}}
                />
              </div>
            </ViewportFrame>
          </PreviewThemeWrapper>
        )}
      </div>
    </LibraryPreviewPanel>
  );
}

/* ---- Variant Gallery Section ---- */

function VariantGallerySection({
  componentName,
  axis,
}: {
  componentName: string;
  axis: ParsedAxis;
}) {
  const [showCode, setShowCode] = useState(false);

  return (
    <LibraryDocsSection
      eyebrow="Variants"
      title={`${axis.axis.charAt(0).toUpperCase()}${axis.axis.slice(1)}`}
      actions={
        <button
          type="button"
          onClick={() => setShowCode(!showCode)}
          className="flex items-center gap-1.5 rounded-lg border border-border-subtle bg-surface-default/80 px-2.5 py-1.5 text-xs font-medium text-text-secondary backdrop-blur-xs transition hover:bg-surface-default hover:text-text-primary"
        >
          {showCode ? (
            <>
              <Eye className="h-3.5 w-3.5" /> Preview
            </>
          ) : (
            <>
              <Code2 className="h-3.5 w-3.5" /> Code
            </>
          )}
        </button>
      }
    >
      {showCode ? (
        <div className="flex flex-col gap-3">
          {axis.values.map((val) => (
            <LibraryCodeBlock
              key={val}
              code={generateCodeSnippet(
                componentName,
                { [axis.axis]: val },
                "Click me",
              )}
              languageLabel="tsx"
            />
          ))}
        </div>
      ) : (
        <div className={
          COMPLEX_PREVIEW_COMPONENTS.has(componentName)
            ? "grid grid-cols-1 gap-4 xl:grid-cols-2"
            : "grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4"
        }>
          {axis.values.map((val) => {
            const isComplex = COMPLEX_PREVIEW_COMPONENTS.has(componentName);
            return (
              <div
                key={val}
                className="flex flex-col items-center gap-3 rounded-2xl border border-border-subtle bg-surface-canvas p-4 transition hover:border-action-primary/30 hover:shadow-xs"
                style={isComplex ? { minHeight: 180 } : undefined}
              >
                <div
                  className={isComplex ? "w-full origin-top" : "flex min-h-[48px] items-center justify-center"}
                  style={isComplex ? { zoom: 0.5 } : undefined}
                >
                  <PlaygroundPreview
                    componentName={componentName}
                    propValues={{ [axis.axis]: val }}
                  />
                </div>
                <LibraryDetailLabel>{val}</LibraryDetailLabel>
              </div>
            );
          })}
        </div>
      )}
    </LibraryDocsSection>
  );
}

/* ---- Size Scale Section ---- */

function SizeScaleSection({
  componentName,
  sizes,
}: {
  componentName: string;
  sizes: string[];
}) {
  return (
    <LibraryDocsSection eyebrow="Scale" title="Size Comparison">
      <div className="flex flex-wrap items-end gap-6">
        {sizes.map((size) => (
          <div key={size} className="flex flex-col items-center gap-3">
            <div className="flex items-center justify-center rounded-2xl border border-border-subtle bg-surface-canvas px-6 py-4 transition hover:border-action-primary/30">
              <PlaygroundPreview
                componentName={componentName}
                propValues={{ size }}
              />
            </div>
            <LibraryDetailLabel>{size}</LibraryDetailLabel>
          </div>
        ))}
      </div>
    </LibraryDocsSection>
  );
}

/* ---- State Demonstration Section ---- */

/**
 * Resolves the effective preview states for a component.
 * Priority: explicit previewStates > stateModel entries that exist in STATE_PROP_MAP.
 */
function getEffectivePreviewStates(apiItem: ApiItem | null | undefined): string[] {
  if (!apiItem) return [];
  if (apiItem.previewStates && apiItem.previewStates.length > 0) {
    return apiItem.previewStates;
  }
  // Fallback: filter stateModel to only entries that have a STATE_PROP_MAP mapping
  return (apiItem.stateModel ?? []).filter((s) => STATE_PROP_MAP[s] !== undefined);
}

/**
 * Returns the behavior/interaction model descriptions for docs display.
 * Priority: explicit behaviorModel > stateModel entries that are NOT in STATE_PROP_MAP.
 */
function getEffectiveBehaviorModel(apiItem: ApiItem | null | undefined): string[] {
  if (!apiItem) return [];
  if (apiItem.behaviorModel && apiItem.behaviorModel.length > 0) {
    return apiItem.behaviorModel;
  }
  // Fallback: stateModel entries that are NOT preview-mappable
  return (apiItem.stateModel ?? []).filter((s) => STATE_PROP_MAP[s] === undefined);
}

// Imported from shared module — single source of truth for state→prop mappings.
// Also consumed by state-preview-contract.test.ts for drift detection.

/**
 * Checks whether a component natively supports a given state.
 *
 * If the state comes from explicit `previewStates` metadata, it is considered native
 * because previewStates should only contain states the component actually implements.
 *
 * For legacy stateModel fallback, we fall back to checking docs prop list intersection
 * (less reliable, but better than no check).
 */
function isStateNativelySupported(
  state: string,
  isFromExplicitPreviewStates: boolean,
  componentProps: Set<string>,
): boolean {
  // Explicit previewStates are curated — trust them as native
  if (isFromExplicitPreviewStates) return true;

  // Fallback: check STATE_PROP_MAP keys against docs props
  const stateProps = STATE_PROP_MAP[state];
  if (!stateProps) return false;

  const propKeys = Object.keys(stateProps);
  if (propKeys.length === 0) return true;

  return propKeys.some((key) => componentProps.has(key));
}

function StateDemoSection({
  componentName,
  states,
  componentProps,
  isExplicitPreviewStates,
}: {
  componentName: string;
  states: string[];
  componentProps?: Set<string>;
  /** True if states came from explicit previewStates field (not stateModel fallback) */
  isExplicitPreviewStates?: boolean;
}) {
  const displayStates = states.filter((s) => s !== "full");

  if (displayStates.length === 0) return null;

  const isComplex = COMPLEX_PREVIEW_COMPONENTS.has(componentName);
  const propSet = componentProps ?? new Set<string>();

  return (
    <LibraryDocsSection eyebrow="States" title="State Demonstrations">
      <div className={
        isComplex
          ? "grid grid-cols-1 gap-4 xl:grid-cols-2"
          : "grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4"
      }>
        {/* Normal state */}
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-border-subtle bg-surface-canvas p-4"
          style={isComplex ? { minHeight: 180 } : undefined}
        >
          <div
            className={isComplex ? "w-full origin-top" : "flex min-h-[48px] items-center justify-center"}
            style={isComplex ? { zoom: 0.5 } : undefined}
          >
            <PlaygroundPreview
              componentName={componentName}
              propValues={{}}
              compact
            />
          </div>
          <LibraryDetailLabel>Normal</LibraryDetailLabel>
        </div>

        {/* Each state with StatePreviewWrapper */}
        {displayStates.map((state) => {
          const stateProps = STATE_PROP_MAP[state] ?? {};
          const isNative = isStateNativelySupported(state, !!isExplicitPreviewStates, propSet);

          // Subtle card tint per state category for visual differentiation
          const cardTint =
            state === "disabled" || state === "hidden"
              ? "border-state-danger-border/40 bg-state-danger-bg/40"
              : state === "readonly" || state === "readOnly"
                ? "border-state-warning-border/40 bg-state-warning-bg/40"
                : state === "error" || state === "invalid"
                  ? "border-state-danger-border/30 bg-state-danger-bg/30"
                  : state === "loading"
                    ? "border-state-info-border/30 bg-state-info-bg/30"
                    : state === "checked" || state === "selected" || state === "active" || state === "success" || state === "approved"
                      ? "border-state-success-border/30 bg-state-success-bg/30"
                      : "border-border-subtle bg-surface-canvas";

          return (
            <div
              key={state}
              className={`flex flex-col items-center gap-3 rounded-2xl border p-4 ${cardTint}`}
              style={isComplex ? { minHeight: 180 } : undefined}
            >
              <div
                className={isComplex ? "w-full origin-top" : "flex min-h-[48px] items-center justify-center"}
                style={isComplex ? { zoom: 0.5 } : undefined}
              >
                <StatePreviewWrapper state={state} isNativelySupported={isNative}>
                  <PlaygroundPreview
                    componentName={componentName}
                    propValues={stateProps as Record<string, string | boolean | number>}
                    compact
                  />
                </StatePreviewWrapper>
              </div>
              <LibraryDetailLabel>{state}</LibraryDetailLabel>
            </div>
          );
        })}
      </div>
    </LibraryDocsSection>
  );
}

/* ================================================================== */
/*  API Tab                                                            */
/* ================================================================== */

function ApiTab({ apiItem, componentName }: { apiItem: ApiItem; componentName?: string }) {
  const { t } = useDesignLab();

  if (!apiItem || (apiItem.props ?? []).length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-border-subtle bg-surface-canvas py-16">
        <FileCode2 className="mb-3 h-8 w-8 text-text-secondary/40" />
        <Text variant="secondary">
          {t("designlab.detail.api.empty")}
        </Text>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Prop count header */}
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-state-info-bg">
          <FileCode2 className="h-4 w-4 text-state-info-text" />
        </div>
        <div>
          <Text as="div" className="text-sm font-semibold text-text-primary">
            Component API
          </Text>
          <Text variant="secondary" className="text-xs">
            {(apiItem.props ?? []).length} props &middot; {(apiItem.props ?? []).filter((p: { required: boolean }) => p.required).length} required
          </Text>
        </div>
      </div>

      <PropsTableV2
        props={apiItem.props ?? []}
        componentName={componentName ?? apiItem.name}
      />

      {/* Props Dependency Graph */}
      <PropsDepsGraph componentName={componentName ?? apiItem.name} />
    </div>
  );
}

/* ================================================================== */
/*  Examples Tab — Auto-generated usage examples with live previews    */
/* ================================================================== */

function ComponentExamplesTab({
  componentName,
  apiItem,
  importStatement,
}: {
  componentName: string;
  apiItem: ApiItem;
  importStatement?: string;
}) {
  const parsedAxes = useMemo(
    () => parseVariantAxes(apiItem?.variantAxes ?? []),
    [apiItem?.variantAxes],
  );

  const hasVariants = parsedAxes.length > 0;
  const effectivePreviewStates = getEffectivePreviewStates(apiItem);
  const hasStates = effectivePreviewStates.length > 0;
  const previewFocus = apiItem?.previewFocus ?? [];

  return (
    <div className="flex flex-col gap-8">
      {/* Basic Usage */}
      <ExampleCard
        title="Basic Usage"
        description={`The simplest way to use the ${componentName} component.`}
        componentName={componentName}
        propOverrides={{}}
        importStatement={importStatement}
      />

      {/* Variant examples — first axis only */}
      {hasVariants && parsedAxes[0] && (
        <ExampleCard
          title={`${parsedAxes[0].axis.charAt(0).toUpperCase()}${parsedAxes[0].axis.slice(1)} Variants`}
          description={`All available ${parsedAxes[0].axis} options for ${componentName}.`}
          componentName={componentName}
          propOverrides={{ [parsedAxes[0].axis]: parsedAxes[0].values[0] }}
          importStatement={importStatement}
          multiVariants={parsedAxes[0]}
        />
      )}

      {/* Disabled state example */}
      {hasStates && effectivePreviewStates.includes("disabled") && (
        <ExampleCard
          title="Disabled State"
          description={`${componentName} in disabled state prevents user interaction.`}
          componentName={componentName}
          propOverrides={{ disabled: true }}
          importStatement={importStatement}
        />
      )}

      {/* Loading state example */}
      {hasStates && effectivePreviewStates.includes("loading") && (
        <ExampleCard
          title="Loading State"
          description={`${componentName} with loading indicator.`}
          componentName={componentName}
          propOverrides={{ loading: true }}
          importStatement={importStatement}
        />
      )}

      {/* Preview focus scenarios */}
      {previewFocus.map((scenario, _idx) => (
        <ExampleCard
          key={scenario}
          title={scenario}
          description={`Demonstration of "${scenario}" scenario.`}
          componentName={componentName}
          propOverrides={{}}
          importStatement={importStatement}
        />
      ))}
    </div>
  );
}

/* ---- Example Card ---- */

function ExampleCard({
  title,
  description,
  componentName,
  propOverrides,
  importStatement,
  multiVariants,
}: {
  title: string;
  description: string;
  componentName: string;
  propOverrides: Record<string, string | boolean | number>;
  importStatement?: string;
  multiVariants?: ParsedAxis;
}) {
  const [showCode, setShowCode] = useState(false);
  const [appearance, setAppearance] = useState<PreviewAppearance>("light");
  const [viewport, setViewport] = useState<PreviewViewport>("desktop");

  const code = useMemo(() => {
    const importLine = importStatement
      ? `${importStatement}\n\n`
      : `import { ${componentName} } from '@mfe/design-system';\n\n`;

    if (multiVariants) {
      const snippets = multiVariants.values
        .map((val) =>
          generateCodeSnippet(
            componentName,
            { ...propOverrides, [multiVariants.axis]: val },
            "Click me",
          ),
        )
        .join("\n");
      return `${importLine}${snippets}`;
    }

    return `${importLine}${generateCodeSnippet(componentName, propOverrides, "Click me")}`;
  }, [componentName, propOverrides, importStatement, multiVariants]);

  return (
    <div className="overflow-hidden rounded-2xl border border-border-subtle bg-surface-default">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border-subtle px-5 py-3">
        <div className="min-w-0">
          <Text as="div" className="text-sm font-semibold text-text-primary">
            {title}
          </Text>
          <Text variant="secondary" className="mt-0.5 text-xs">
            {description}
          </Text>
        </div>
        <div className="flex items-center gap-2">
          <PreviewToolbar
            appearance={appearance}
            viewport={viewport}
            onAppearanceChange={setAppearance}
            onViewportChange={setViewport}
            hideViewport
          />
          <button
            type="button"
            onClick={() => setShowCode(!showCode)}
            className="flex items-center gap-1.5 rounded-lg border border-border-subtle px-2.5 py-1.5 text-xs font-medium text-text-secondary transition hover:text-text-primary"
          >
            {showCode ? (
              <>
                <Eye className="h-3.5 w-3.5" /> Preview
              </>
            ) : (
              <>
                <Code2 className="h-3.5 w-3.5" /> Code
              </>
            )}
          </button>
        </div>
      </div>

      {/* Preview */}
      <PreviewThemeWrapper
        appearance={appearance}
        className="p-8"
      >
        <ViewportFrame viewport={viewport}>
          {multiVariants ? (
            <div className="flex flex-wrap items-center justify-center gap-4">
              {multiVariants.values.map((val) => (
                <div key={val} className="flex flex-col items-center gap-2">
                  <PlaygroundPreview
                    componentName={componentName}
                    propValues={{
                      ...propOverrides,
                      [multiVariants.axis]: val,
                    }}
                  />
                  <Text variant="secondary" className="text-[10px] uppercase tracking-wider">
                    {val}
                  </Text>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-center">
              <PlaygroundPreview
                componentName={componentName}
                propValues={propOverrides}
              />
            </div>
          )}
        </ViewportFrame>
      </PreviewThemeWrapper>

      {/* Code panel */}
      {showCode && (
        <div className="border-t border-border-subtle">
          <CodeBlock
            code={code}
            language="tsx"
            variant="dark"
            label="TSX"
            className="rounded-none! border-0!"
          />
        </div>
      )}
    </div>
  );
}

/* ================================================================== */
/*  Quality Tab — Gates + A11y Scorecard + Regression Focus            */
/* ================================================================== */

/* ── Component category classification for a11y scoring ── */
type ComponentCategory = "interactive" | "form-field" | "display" | "container" | "overlay";

const DISPLAY_COMPONENTS = new Set([
  "Divider", "Skeleton", "Spinner", "Badge", "Tag", "Text", "Avatar", "Card", "Stack",
  "Alert", "ConfidenceBadge", "Descriptions", "DetailSummary", "EntitySummaryBlock",
  "SummaryStrip", "NotificationItemCard", "JsonViewer", "Timeline", "QRCode", "Watermark",
  "AvatarGroup", "ThemePresetCompare", "ThemePresetGallery", "ThemePreviewCard",
  "AIActionAuditTimeline", "CitationPanel", "RecommendationCard", "PageHeader",
  "Empty", "EmptyState", "EmptyErrorLoading", "List", "TableSimple",
  "ActionHeader", "Action Header", "AppHeader", "App Header",
]);
const FORM_FIELDS = new Set([
  "Input", "TextInput", "Textarea", "TextArea", "Select", "Checkbox", "Switch", "Radio",
  "SearchInput", "Slider", "Combobox", "DatePicker", "TimePicker",
  "AutoComplete", "Cascader", "ColorPicker", "InputNumber", "Mentions",
  "Rating", "Transfer", "Upload",
]);
const INTERACTIVE = new Set([
  "Button", "IconButton", "LinkInline", "Tabs", "Accordion", "Pagination", "Dropdown",
  "Steps", "Breadcrumb", "MenuBar", "NavigationRail", "MobileStepper", "TablePagination",
  "SectionTabs", "DetailSectionTabs", "Segmented", "Tree", "TreeTable",
  "FilterBar", "ReportFilterPanel", "ActionBar", "Action Bar", "AnchorToc",
  "DesktopMenubar", "Desktop Menubar", "NavigationMenu", "Navigation Menu",
  "FloatButton", "Carousel", "Calendar", "CommandPalette",
  "CommandHeader", "Search / Command Header",
  "PromptComposer", "AIGuidedAuthoring", "ApprovalCheckpoint", "ApprovalReview",
]);
const OVERLAY = new Set([
  "Dialog", "Modal", "Popover", "Tooltip", "Drawer",
  "DetailDrawer", "FormDrawer", "NotificationDrawer", "ContextMenu",
  "TourCoachmarks", "Toast", "ToastProvider",
]);
const CONTAINER_COMPONENTS = new Set([
  "PageLayout", "SearchFilterListing", "EntityGridTemplate", "AgGridServer",
  "MasterDetail", "SmartDashboard", "NotificationPanel", "ErrorBoundary",
  "CommandWorkspace", "Command Workspace",
  "CrudTemplate", "CRUD Template",
  "DashboardTemplate", "Dashboard Template",
  "DetailTemplate", "Detail Template",
  "SettingsTemplate", "Settings Template",
]);

function getComponentCategory(name: string): ComponentCategory {
  if (FORM_FIELDS.has(name)) return "form-field";
  if (INTERACTIVE.has(name)) return "interactive";
  if (OVERLAY.has(name)) return "overlay";
  if (CONTAINER_COMPONENTS.has(name)) return "container";
  if (DISPLAY_COMPONENTS.has(name)) return "display";
  return "display"; // default — uncategorized items use minimal criteria
}

/** Categories applicable per component type
 * - display: only Semantics — passive content, no interaction needed
 * - interactive: Semantics + Keyboard + Visual — children provide accessible name, no explicit label needed
 * - form-field: all categories — full a11y requirements
 * - overlay: Labelling + Semantics + Keyboard — needs title/label, focus trap, escape
 * - container: only Semantics — layout wrappers
 */
const APPLICABLE_CATEGORIES: Record<ComponentCategory, Set<string>> = {
  "display": new Set(["Semantics"]),
  "interactive": new Set(["Semantics", "Keyboard", "Visual"]),
  "form-field": new Set(["Labelling", "Semantics", "Keyboard", "States", "Visual"]),
  "overlay": new Set(["Labelling", "Semantics", "Keyboard"]),
  "container": new Set(["Semantics"]),
};

function QualityTab({
  indexItem,
  apiItem,
}: {
  indexItem: IndexItem;
  apiItem: ApiItem;
}) {
  const { t } = useDesignLab();
  const regressionFocus = apiItem?.regressionFocus ?? [];

  const componentCategory = getComponentCategory(indexItem.name);
  const applicableCategories = APPLICABLE_CATEGORIES[componentCategory];

  /* Infer a11y indicators from props and state model */
  const a11yChecks = useMemo(() => {
    const props = apiItem?.props ?? [];
    const states = apiItem?.stateModel ?? [];
    const checks: { label: string; pass: boolean | "na"; category: string }[] = [];

    const isApplicable = (cat: string) => applicableCategories.has(cat);
    const isFormField = componentCategory === "form-field";
    const isInteractive = componentCategory === "interactive";
    const isDisplay = componentCategory === "display";
    const isContainer = componentCategory === "container";
    const isOverlay = componentCategory === "overlay";

    /* Auto-credit flags: native HTML elements provide implicit a11y capabilities
     * - form-field: <input>, <select>, <textarea> → implicit role, keyboard, ARIA
     * - interactive: <button>, <a>, <nav> → implicit role, keyboard
     * - display: <span>, <hr>, <img> → implicit semantics via rendered content
     * - container: <div>, <section> → implicit semantic structure
     * - overlay: <dialog> → implicit role */
    const hasNativeSemantics = isFormField || isInteractive || isDisplay || isContainer || isOverlay;
    const hasNativeKeyboard = isFormField || isInteractive || isOverlay;

    /* Labelling — fuzzy prop matching */
    const hasAriaLabel = props.some(
      (p) => p.name === "label" || p.name.includes("label") || p.name === "title" || p.name === "aria-label" || p.name === "ariaLabel" || p.name.includes("aria-label"),
    );
    checks.push({ label: "Accessible label (aria-label / label prop)", pass: isApplicable("Labelling") ? hasAriaLabel : "na", category: "Labelling" });

    const hasAriaDescribedBy = props.some(
      (p) => p.name.includes("description") || p.name.includes("help") || p.name.includes("aria-describedby"),
    );
    checks.push({ label: "Description / help text support", pass: isApplicable("Labelling") ? hasAriaDescribedBy : "na", category: "Labelling" });

    /* Semantics — components using native HTML elements get auto-credit for implicit ARIA roles */
    const hasRole = hasNativeSemantics || props.some((p) => p.name === "role" || p.name.includes("role"));
    checks.push({ label: "ARIA role prop", pass: isApplicable("Semantics") ? hasRole : "na", category: "Semantics" });

    const hasAriaProps = hasNativeSemantics || props.some((p) => p.name.includes("aria-") || p.name.startsWith("aria"));
    checks.push({ label: "ARIA attribute support", pass: isApplicable("Semantics") ? hasAriaProps : "na", category: "Semantics" });

    /* Keyboard — native interactive/form elements are keyboard-accessible by default */
    const hasKeyboard = hasNativeKeyboard || props.some(
      (p) => p.name.includes("onKey") || p.name.includes("tabIndex") || p.name.includes("autoFocus"),
    );
    checks.push({ label: "Keyboard interaction support", pass: isApplicable("Keyboard") ? hasKeyboard : "na", category: "Keyboard" });

    const hasTabIndex = hasNativeKeyboard || props.some((p) => p.name.includes("tabIndex"));
    checks.push({ label: "Tab index management", pass: isApplicable("Keyboard") ? hasTabIndex : "na", category: "Keyboard" });

    /* States — fuzzy matching on both props and stateModel */
    const hasDisabled =
      states.some((s) => s.toLowerCase().includes("disabled")) || props.some((p) => p.name.includes("disabled"));
    checks.push({ label: "Disabled state support", pass: isApplicable("States") ? hasDisabled : "na", category: "States" });

    const hasReadOnly =
      states.some((s) => s.toLowerCase().includes("readonly") || s.toLowerCase().includes("read-only")) ||
      props.some((p) => p.name.includes("readOnly") || p.name.includes("readonly"));
    checks.push({ label: "Read-only state support", pass: isApplicable("States") ? hasReadOnly : "na", category: "States" });

    const hasError =
      states.some((s) => s.toLowerCase().includes("error") || s.toLowerCase().includes("validation")) ||
      props.some((p) => p.name.includes("error") || p.name.includes("status"));
    checks.push({ label: "Error state for validation", pass: isApplicable("States") ? hasError : "na", category: "States" });

    const hasLoading =
      states.some((s) => s.toLowerCase().includes("loading")) || props.some((p) => p.name.includes("loading"));
    checks.push({ label: "Loading state indicator", pass: isApplicable("States") ? hasLoading : "na", category: "States" });

    /* Visual — fuzzy prop matching */
    const hasSize = props.some((p) => p.name === "size" || p.name.toLowerCase().includes("size"));
    checks.push({ label: "Size variants (touch target sizing)", pass: isApplicable("Visual") ? hasSize : "na", category: "Visual" });

    return checks;
  }, [apiItem, applicableCategories, componentCategory]);

  const applicableChecks = a11yChecks.filter((c) => c.pass !== "na");
  const a11yScore = applicableChecks.filter((c) => c.pass === true).length;
  const a11yTotal = applicableChecks.length;

  return (
    <div className="flex flex-col gap-6">
      {/* ── A11y Scorecard — Modern card with categories ── */}
      <div className="overflow-hidden rounded-2xl border border-border-subtle bg-surface-default">
        <div className="flex items-center justify-between border-b border-border-subtle bg-linear-to-r from-action-primary/5 to-transparent px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-action-primary/10">
              <ShieldCheck className="h-4 w-4 text-action-primary" />
            </div>
            <div>
              <Text as="div" className="text-sm font-semibold text-text-primary">
                Accessibility Scorecard
              </Text>
              <Text variant="secondary" className="text-[10px]">
                {a11yScore >= a11yTotal * 0.8
                  ? "Excellent coverage"
                  : a11yScore >= a11yTotal * 0.5
                    ? "Good — room for improvement"
                    : "Needs attention"}
              </Text>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Progress ring */}
            <div className="relative flex h-12 w-12 items-center justify-center">
              <svg className="h-12 w-12 -rotate-90" viewBox="0 0 44 44">
                <circle cx="22" cy="22" r="18" fill="none" stroke="currentColor" strokeWidth="3" className="text-surface-muted" />
                <circle
                  cx="22" cy="22" r="18" fill="none" strokeWidth="3"
                  strokeDasharray={`${(a11yTotal > 0 ? a11yScore / a11yTotal : 0) * 113.1} 113.1`}
                  strokeLinecap="round"
                  className={a11yTotal === 0 ? "text-surface-muted" : a11yScore === a11yTotal ? "text-state-success-text" : a11yScore >= a11yTotal / 2 ? "text-state-warning-text" : "text-state-danger-text"}
                />
              </svg>
              <span className="absolute text-[10px] font-bold tabular-nums text-text-primary">
                {a11yTotal > 0 ? Math.round((a11yScore / a11yTotal) * 100) : 0}%
              </span>
            </div>
          </div>
        </div>
        {/* Grouped checks */}
        {(["Labelling", "Semantics", "Keyboard", "States", "Visual"] as const).map((cat) => {
          const catChecks = a11yChecks.filter((c) => c.category === cat);
          if (catChecks.length === 0) return null;
          const catApplicable = catChecks.filter((c) => c.pass !== "na");
          const catPassing = catChecks.filter((c) => c.pass === true).length;
          const allNA = catApplicable.length === 0;
          return (
            <div key={cat}>
              <div className="flex items-center justify-between bg-surface-canvas/40 px-5 py-2">
                <Text variant="secondary" className="text-[10px] font-semibold uppercase tracking-widest">
                  {cat}
                </Text>
                <Text variant="secondary" className="text-[10px] font-semibold tabular-nums">
                  {allNA ? "N/A" : `${catPassing}/${catApplicable.length}`}
                </Text>
              </div>
              <div className="divide-y divide-border-subtle">
                {catChecks.map((check) => (
                  <div
                    key={check.label}
                    className="flex items-center gap-3 px-5 py-2.5 transition-colors hover:bg-surface-canvas/30"
                  >
                    {check.pass === "na" ? (
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-surface-muted">
                        <span className="text-[9px] font-semibold text-text-tertiary">N/A</span>
                      </span>
                    ) : check.pass ? (
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-state-success-bg">
                        <Check className="h-3 w-3 text-state-success-text" />
                      </span>
                    ) : (
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-state-danger-bg">
                        <span className="h-1.5 w-1.5 rounded-full bg-state-danger-text" />
                      </span>
                    )}
                    <Text className={`text-xs ${check.pass === "na" ? "text-text-tertiary" : "text-text-primary"}`}>{check.label}</Text>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* ── Enterprise-Ready Checklist ── */}
      <EnterpriseReadyChecklist indexItem={indexItem} apiItem={apiItem} componentCategory={componentCategory} />

      {/* ── Quality Gates ── */}
      <div className="overflow-hidden rounded-2xl border border-border-subtle bg-surface-default">
        <div className="flex items-center gap-3 border-b border-border-subtle bg-linear-to-r from-state-success-bg to-transparent px-5 py-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-state-success-bg">
            <ShieldCheck className="h-4 w-4 text-state-success-text" />
          </div>
          <Text as="div" className="text-sm font-semibold text-text-primary">
            {t("designlab.detail.quality.gates")}
          </Text>
        </div>
        {(indexItem?.qualityGates ?? []).length > 0 ? (
          <div className="divide-y divide-border-subtle">
            {(indexItem?.qualityGates ?? []).map((gate) => (
              <div
                key={gate}
                className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-surface-canvas/30"
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-state-success-bg">
                  <Check className="h-3 w-3 text-state-success-text" />
                </span>
                <Text className="text-xs text-text-primary">{gate}</Text>
              </div>
            ))}
          </div>
        ) : (
          <div className="px-5 py-6 text-center">
            <Text variant="secondary" className="text-xs">
              {t("designlab.detail.quality.noGates")}
            </Text>
          </div>
        )}
      </div>

      {/* ── Regression Focus ── */}
      {regressionFocus.length > 0 && (
        <div className="overflow-hidden rounded-2xl border border-border-subtle bg-surface-default">
          <div className="flex items-center gap-3 border-b border-border-subtle bg-linear-to-r from-state-warning-bg to-transparent px-5 py-4">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-state-warning-bg">
              <Eye className="h-4 w-4 text-state-warning-text" />
            </div>
            <Text as="div" className="text-sm font-semibold text-text-primary">
              Regression Focus Areas
            </Text>
            <span className="rounded-full bg-state-warning-bg px-2 py-0.5 text-[10px] font-semibold tabular-nums text-state-warning-text">
              {regressionFocus.length}
            </span>
          </div>
          <div className="divide-y divide-border-subtle">
            {regressionFocus.map((focus) => (
              <div
                key={focus}
                className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-surface-canvas/30"
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-state-warning-bg">
                  <span className="h-1.5 w-1.5 rounded-full bg-state-warning-text" />
                </span>
                <Text className="text-xs text-text-primary">{focus}</Text>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── KPI Metric Cards ── */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="group relative overflow-hidden rounded-2xl border border-border-subtle bg-surface-default p-5 text-center transition-all duration-300 hover:border-border-default hover:shadow-xs">
          <Text variant="secondary" className="text-[10px] font-semibold uppercase tracking-widest">
            Lifecycle
          </Text>
          <Text as="div" className={[
            "mt-2 text-xl font-extrabold capitalize",
            indexItem.lifecycle === "stable" ? "text-state-success-text" : indexItem.lifecycle === "beta" ? "text-state-warning-text" : "text-state-info-text",
          ].join(" ")}>
            {indexItem.lifecycle}
          </Text>
          <div className="pointer-events-none absolute -bottom-3 -right-3 h-12 w-12 rounded-full bg-linear-to-tl from-action-primary/5 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
        </div>
        <div className="group relative overflow-hidden rounded-2xl border border-border-subtle bg-surface-default p-5 text-center transition-all duration-300 hover:border-border-default hover:shadow-xs">
          <Text variant="secondary" className="text-[10px] font-semibold uppercase tracking-widest">
            Maturity
          </Text>
          <Text as="div" className={[
            "mt-2 text-xl font-extrabold capitalize",
            indexItem.maturity === "enterprise" ? "text-action-primary" : indexItem.maturity === "stable" ? "text-state-success-text" : indexItem.maturity === "beta" ? "text-state-warning-text" : "text-state-info-text",
          ].join(" ")}>
            {indexItem.maturity ? `${indexItem.maturity === "enterprise" ? "🏢" : indexItem.maturity === "stable" ? "✅" : indexItem.maturity === "beta" ? "🔶" : "🧪"} ${indexItem.maturity}` : "—"}
          </Text>
          <div className="pointer-events-none absolute -bottom-3 -right-3 h-12 w-12 rounded-full bg-linear-to-tl from-action-primary/5 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
        </div>
        <div className="group relative overflow-hidden rounded-2xl border border-border-subtle bg-surface-default p-5 text-center transition-all duration-300 hover:border-border-default hover:shadow-xs">
          <Text variant="secondary" className="text-[10px] font-semibold uppercase tracking-widest">
            Props Count
          </Text>
          <Text as="div" className="mt-2 text-xl font-extrabold tabular-nums text-state-info-text">
            {apiItem?.props?.length ?? 0}
          </Text>
          <div className="pointer-events-none absolute -bottom-3 -right-3 h-12 w-12 rounded-full bg-linear-to-tl from-action-primary/5 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
        </div>
        <div className="group relative overflow-hidden rounded-2xl border border-border-subtle bg-surface-default p-5 text-center transition-all duration-300 hover:border-border-default hover:shadow-xs">
          <Text variant="secondary" className="text-[10px] font-semibold uppercase tracking-widest">
            Where Used
          </Text>
          <Text as="div" className="mt-2 text-xl font-extrabold tabular-nums text-action-primary">
            {(indexItem?.whereUsed ?? []).length}
          </Text>
          <div className="pointer-events-none absolute -bottom-3 -right-3 h-12 w-12 rounded-full bg-linear-to-tl from-action-primary/5 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
        </div>
        <div className="group relative overflow-hidden rounded-2xl border border-border-subtle bg-surface-default p-5 text-center transition-all duration-300 hover:border-border-default hover:shadow-xs">
          <Text variant="secondary" className="text-[10px] font-semibold uppercase tracking-widest">
            Bundle Impact
          </Text>
          <Text as="div" className="mt-2 text-xl font-extrabold tabular-nums text-state-danger-text">
            {estimateBundleSize(indexItem.name, apiItem?.props?.length ?? 0)}
          </Text>
          <Text variant="secondary" className="mt-0.5 text-[9px]">
            gzip estimate
          </Text>
          <div className="pointer-events-none absolute -bottom-3 -right-3 h-12 w-12 rounded-full bg-linear-to-tl from-action-primary/5 to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
        </div>
      </div>

      {/* ── Component Complexity Breakdown ── */}
      <div className="overflow-hidden rounded-2xl border border-border-subtle bg-surface-default">
        <div className="flex items-center gap-3 border-b border-border-subtle bg-linear-to-r from-state-info-bg to-transparent px-5 py-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-state-info-bg">
            <Code2 className="h-4 w-4 text-state-info-text" />
          </div>
          <Text as="div" className="text-sm font-semibold text-text-primary">
            Component Complexity
          </Text>
        </div>
        <div className="grid divide-x divide-border-subtle sm:grid-cols-3">
          <ComplexityMetric
            label="Props"
            value={apiItem?.props?.length ?? 0}
            max={40}
            color="blue"
          />
          <ComplexityMetric
            label="Variants"
            value={apiItem?.variantAxes?.length ?? 0}
            max={8}
            color="violet"
          />
          <ComplexityMetric
            label="States"
            value={getEffectivePreviewStates(apiItem).length}
            max={6}
            color="amber"
          />
        </div>
      </div>
    </div>
  );
}

/* ---- Bundle size estimation (heuristic) ---- */

const KNOWN_SIZES: Record<string, string> = {
  Text: "0.4 KB", Button: "1.2 KB", IconButton: "0.9 KB", Badge: "0.3 KB",
  Tag: "0.4 KB", Avatar: "0.8 KB", Spinner: "0.3 KB", Skeleton: "0.4 KB",
  Divider: "0.2 KB", Input: "1.1 KB", TextInput: "1.1 KB", Textarea: "0.9 KB",
  Select: "2.1 KB", Checkbox: "0.6 KB", Radio: "0.5 KB", Switch: "0.7 KB",
  Slider: "1.4 KB", Tooltip: "1.3 KB", Popover: "1.5 KB", Alert: "0.8 KB",
  Modal: "2.5 KB", Dialog: "2.2 KB", Tabs: "1.8 KB", Accordion: "1.6 KB",
  Steps: "1.4 KB", Breadcrumb: "0.7 KB", Pagination: "1.5 KB",
  Segmented: "1.1 KB", NavigationRail: "1.2 KB", MenuBar: "1.5 KB",
  Dropdown: "1.8 KB", ContextMenu: "1.6 KB", CommandPalette: "3.8 KB",
  FormField: "1.0 KB", SearchInput: "1.3 KB", Combobox: "2.4 KB",
  DatePicker: "3.2 KB", TimePicker: "2.8 KB", Upload: "2.1 KB",
  TableSimple: "2.6 KB", List: "1.2 KB", Tree: "2.4 KB", TreeTable: "4.5 KB",
  JsonViewer: "2.2 KB", Descriptions: "1.0 KB", EmptyState: "0.6 KB",
  EmptyErrorLoading: "0.8 KB", Card: "0.5 KB", FormDrawer: "2.8 KB",
  DetailDrawer: "2.6 KB", EntityGrid: "8.5 KB", AgGridServer: "12.0 KB",
};

function estimateBundleSize(name: string, propCount: number): string {
  if (KNOWN_SIZES[name]) return KNOWN_SIZES[name];
  const est = Math.max(0.3, propCount * 0.08);
  return `~${est.toFixed(1)} KB`;
}

/* ---- Complexity Metric bar ---- */

function ComplexityMetric({
  label,
  value,
  max,
  color,
}: {
  label: string;
  value: number;
  max: number;
  color: "blue" | "violet" | "amber";
}) {
  const pct = Math.min((value / max) * 100, 100);
  const colorMap = {
    blue: { bar: "bg-state-info-text", text: "text-state-info-text", light: "bg-state-info-bg" },
    violet: { bar: "bg-action-primary", text: "text-action-primary", light: "bg-action-primary/10" },
    amber: { bar: "bg-state-warning-text", text: "text-state-warning-text", light: "bg-state-warning-bg" },
  };
  const c = colorMap[color];

  return (
    <div className="flex flex-col items-center gap-2 px-5 py-4">
      <Text variant="secondary" className="text-[10px] font-semibold uppercase tracking-widest">
        {label}
      </Text>
      <Text as="div" className={`text-2xl font-extrabold tabular-nums ${c.text}`}>
        {value}
      </Text>
      <div className={`h-1.5 w-full rounded-full ${c.light}`}>
        <div
          className={`h-1.5 rounded-full ${c.bar} transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/* ================================================================== */
/*  ChangelogTab — Per-component version history timeline              */
/* ================================================================== */

type ChangelogEntry = {
  version: string;
  date: string;
  type: "feature" | "fix" | "breaking" | "deprecation" | "refactor";
  description: string;
};

const CHANGELOG_TYPE_CONFIG: Record<ChangelogEntry["type"], { label: string; color: string; dot: string }> = {
  feature: { label: "Feature", color: "bg-state-success-bg text-state-success-text", dot: "bg-state-success-text" },
  fix: { label: "Fix", color: "bg-state-info-bg text-state-info-text", dot: "bg-state-info-text" },
  breaking: { label: "Breaking", color: "bg-state-danger-bg text-state-danger-text", dot: "bg-state-danger-text" },
  deprecation: { label: "Deprecated", color: "bg-state-warning-bg text-state-warning-text", dot: "bg-state-warning-text" },
  refactor: { label: "Refactor", color: "bg-action-primary/10 text-action-primary", dot: "bg-action-primary" },
};

/**
 * Changelog data is not yet available.
 * When CHANGELOG.md parsing is implemented, this function will derive
 * entries from the actual file for each component.
 */
function generateComponentChangelog(_componentName: string): ChangelogEntry[] {
  // No simulated data — return empty until CHANGELOG.md integration is built
  return [];
}

function ChangelogTab({ componentName }: { componentName: string }) {
  const entries = useMemo(() => generateComponentChangelog(componentName), [componentName]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <Text as="div" variant="secondary" className="text-[10px] font-semibold uppercase tracking-[0.18em]">
          Version History
        </Text>
        <Text variant="secondary" className="text-xs">
          {entries.length} releases
        </Text>
      </div>

      {entries.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-border-subtle bg-surface-default py-12 px-6 text-center">
          <Clock className="h-8 w-8 text-[var(--text-subtle)]" />
          <Text className="mt-3 text-sm font-medium text-text-primary">
            Değişiklik günlüğü henüz mevcut değil
          </Text>
          <Text variant="secondary" className="mt-1 text-xs max-w-sm">
            CHANGELOG.md dosyasından otomatik oluşturulacak.
          </Text>
        </div>
      ) : (
        /* Timeline */
        <div className="relative">
          {/* Vertical line */}
          <div className="absolute left-[15px] top-2 bottom-2 w-px bg-border-subtle" />

          <div className="">
            {entries.map((entry, i) => {
              const cfg = CHANGELOG_TYPE_CONFIG[entry.type];
              const isFirst = i === 0;
              return (
                <div key={`${entry.version}-${i}`} className="relative flex gap-4 py-3">
                  {/* Dot on timeline */}
                  <div className="relative z-10 flex h-[30px] w-[30px] shrink-0 items-center justify-center">
                    <div className={["h-3 w-3 rounded-full ring-4 ring-surface-default", cfg.dot, isFirst ? "h-3.5 w-3.5" : ""].join(" ")} />
                  </div>

                  {/* Content */}
                  <div className={["min-w-0 flex-1 rounded-xl border border-border-subtle bg-surface-default px-4 py-3 transition", isFirst ? "ring-1 ring-action-primary/20" : ""].join(" ")}>
                    <div className="flex items-center gap-2">
                      <Text className="text-sm font-bold text-text-primary">
                        v{entry.version}
                      </Text>
                      <span className={["rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase", cfg.color].join(" ")}>
                        {cfg.label}
                      </span>
                      {isFirst && (
                        <span className="rounded-md bg-action-primary/10 px-1.5 py-0.5 text-[10px] font-semibold text-action-primary">
                          Latest
                        </span>
                      )}
                      <Text variant="secondary" className="ml-auto text-[11px]">
                        {entry.date}
                      </Text>
                    </div>
                    <Text variant="secondary" className="mt-1 text-sm">
                      {entry.description}
                    </Text>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
