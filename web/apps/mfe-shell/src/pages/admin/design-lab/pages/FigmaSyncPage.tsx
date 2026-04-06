import React, { useMemo, useState } from "react";
import {
  RefreshCw,
  Clock,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Palette,
  Type,
  Box,
  Layers,
  ArrowRight,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

/** Figma brand icon — removed from lucide-react >=1.x, inlined as SVG. */
function Figma({ className }: { className?: string }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M5 5.5A3.5 3.5 0 0 1 8.5 2H12v7H8.5A3.5 3.5 0 0 1 5 5.5z" />
      <path d="M12 2h3.5a3.5 3.5 0 1 1 0 7H12V2z" />
      <path d="M12 12.5a3.5 3.5 0 1 1 7 0 3.5 3.5 0 1 1-7 0z" />
      <path d="M5 19.5A3.5 3.5 0 0 1 8.5 16H12v3.5a3.5 3.5 0 1 1-7 0z" />
      <path d="M5 12.5A3.5 3.5 0 0 1 8.5 9H12v7H8.5A3.5 3.5 0 0 1 5 12.5z" />
    </svg>
  );
}
import { Text } from "@mfe/design-system";
import { useDesignLab } from "../DesignLabProvider";
import { DataProvenanceBadge } from "../components/DataProvenanceBadge";

/* ------------------------------------------------------------------ */
/*  FigmaSyncPage — Figma token sync status & drift indicator          */
/*                                                                     */
/*  Reads design-token metadata from the DesignLab index to show:      */
/*  - Last sync timestamp                                              */
/*  - Token counts by category                                         */
/*  - Drift indicator (tokens added/removed/changed since last sync)   */
/*  - Token diff viewer                                                */
/*  Route: /admin/design-lab/figma-sync                                */
/* ------------------------------------------------------------------ */

/* ---- Derived token data from packages/design-system/src/tokens/ ---- */

type SyncStatus = "synced" | "drift" | "error" | "never";
type TokenChange = { token: string; category: string; type: "added" | "removed" | "changed"; before?: string; after?: string };

/**
 * Derived from actual design token build output:
 * - Token files: packages/design-system/src/tokens/ (11 source files)
 * - Built output: packages/design-system/src/tokens/build/tokens.json
 * - CSS custom properties: ~209 in tokens.css (yaklaşık — build zamanında değişebilir)
 * - Categories counted from tokens.json leaf nodes
 */
function useFigmaSyncData() {
  const { index } = useDesignLab();

  return useMemo(() => {
    // Actual token categories & counts derived from tokens.json build output
    const tokenGroups = ["colors", "typography", "spacing", "radius", "motion", "zindex"];
    const tokenCounts: Record<string, number> = {
      colors: 57,       // color.palette + color.semantic in tokens.json
      typography: 25,    // typography tokens in tokens.json
      spacing: 23,       // spacing scale in tokens.json
      radius: 8,         // border-radius tokens in tokens.json
      motion: 10,        // transition/animation tokens in tokens.json
      zindex: 10,        // z-index layer tokens in tokens.json
    };
    // Additional categories in build: elevation(8), opacity(9), density(54), focusRing(5)
    // yaklaşık değer — build zamanında hesaplanır (tokens.css custom property sayısı)
    const totalTokens = 209;

    // No Figma API connection — show "never synced"
    const syncStatus: SyncStatus = "never";

    // No drift data — Figma API not configured
    const changes: TokenChange[] = [];

    return {
      tokenGroups,
      tokenCounts,
      totalTokens,
      lastSyncDate: null as Date | null,
      figmaFileVersion: null as string | null,
      syncStatus,
      changes,
      componentCount: index.items.length,
      // Additional derived metadata
      tokenSourceFiles: 11, // .ts files in tokens/
      cssCustomProperties: 209,
      additionalCategories: ["elevation", "opacity", "density", "focusRing"],
    };
  }, [index]);
}

/* ---- Status badge ---- */

const STATUS_CONFIG: Record<SyncStatus, { label: string; color: string; icon: React.ReactNode }> = {
  synced: { label: "In Sync", color: "bg-state-success-bg text-state-success-text", icon: <CheckCircle2 className="h-4 w-4" /> },
  drift: { label: "Drift Detected", color: "bg-state-warning-bg text-state-warning-text", icon: <AlertTriangle className="h-4 w-4" /> },
  error: { label: "Sync Error", color: "bg-state-danger-bg text-state-danger-text", icon: <XCircle className="h-4 w-4" /> },
  never: { label: "Never Synced", color: "bg-[var(--surface-muted)] text-[var(--text-secondary)]", icon: <Clock className="h-4 w-4" /> },
};

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  colors: <Palette className="h-4 w-4" />,
  typography: <Type className="h-4 w-4" />,
  spacing: <Box className="h-4 w-4" />,
  radius: <Box className="h-4 w-4" />,
  motion: <RefreshCw className="h-4 w-4" />,
  zindex: <Layers className="h-4 w-4" />,
};

const CHANGE_TYPE_STYLES: Record<TokenChange["type"], string> = {
  added: "bg-state-success-bg text-state-success-text",
  removed: "bg-state-danger-bg text-state-danger-text",
  changed: "bg-state-warning-bg text-state-warning-text",
};

/* ---- Stat Card ---- */

function StatCard({ label, value, icon, subtitle }: { label: string; value: string | number; icon: React.ReactNode; subtitle?: string }) {
  return (
    <div className="rounded-2xl border border-border-subtle bg-surface-default p-5">
      <div className="flex items-start justify-between">
        <div>
          <Text variant="secondary" className="text-xs font-medium uppercase tracking-wider">
            {label}
          </Text>
          <Text className="mt-1 text-2xl font-bold text-text-primary">{value}</Text>
          {subtitle && (
            <Text variant="secondary" className="mt-0.5 text-xs">
              {subtitle}
            </Text>
          )}
        </div>
        <div className="rounded-xl bg-surface-muted p-2.5 text-text-secondary">{icon}</div>
      </div>
    </div>
  );
}

/* ---- Token Category Row ---- */

function TokenCategoryRow({ name, count, total }: { name: string; count: number; total: number }) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  return (
    <div className="flex items-center gap-3 py-2">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-surface-muted text-text-secondary">
        {CATEGORY_ICONS[name] ?? <Box className="h-4 w-4" />}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between">
          <Text className="text-sm font-medium capitalize text-text-primary">{name}</Text>
          <Text variant="secondary" className="text-xs tabular-nums">
            {count} tokens
          </Text>
        </div>
        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-surface-muted">
          <div
            className="h-full rounded-full bg-action-primary transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  );
}

/* ---- Diff Viewer ---- */

function _DiffViewer({ changes }: { changes: TokenChange[] }) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  if (changes.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="text-center">
          <CheckCircle2 className="mx-auto h-8 w-8 text-state-success-text" />
          <Text className="mt-2 text-sm font-medium text-text-primary">No Changes</Text>
          <Text variant="secondary" className="mt-1 text-xs">
            Design tokens are perfectly in sync with Figma
          </Text>
        </div>
      </div>
    );
  }

  return (
    <div className="divide-y divide-border-subtle">
      {changes.map((change, i) => {
        const isExpanded = expandedIdx === i;
        return (
          <button
            key={`${change.token}-${i}`}
            type="button"
            onClick={() => setExpandedIdx(isExpanded ? null : i)}
            className="flex w-full items-start gap-3 px-4 py-3 text-left transition hover:bg-surface-muted/50"
          >
            <div className="mt-0.5">
              {isExpanded ? (
                <ChevronDown className="h-3.5 w-3.5 text-text-tertiary" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-text-tertiary" />
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <code className="text-xs font-medium text-text-primary">{change.token}</code>
                <span
                  className={[
                    "rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase",
                    CHANGE_TYPE_STYLES[change.type],
                  ].join(" ")}
                >
                  {change.type}
                </span>
                <Text variant="secondary" className="ml-auto text-[10px] capitalize">
                  {change.category}
                </Text>
              </div>
              {isExpanded && (
                <div className="flex flex-col mt-2 gap-1 rounded-lg bg-surface-canvas p-3">
                  {change.before && (
                    <div className="flex items-center gap-2">
                      <span className="w-12 text-[10px] font-medium text-state-danger-text">Before</span>
                      <code className="text-xs text-text-secondary">{change.before}</code>
                      {change.type === "changed" && change.token.includes("color") && (
                        <span className="h-4 w-4 rounded-xs border border-border-subtle" style={{ backgroundColor: change.before }} />
                      )}
                    </div>
                  )}
                  {change.after && (
                    <div className="flex items-center gap-2">
                      <span className="w-12 text-[10px] font-medium text-state-success-text">After</span>
                      <code className="text-xs text-text-secondary">{change.after}</code>
                      {change.type === "changed" && change.token.includes("color") && (
                        <span className="h-4 w-4 rounded-xs border border-border-subtle" style={{ backgroundColor: change.after }} />
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}

/* ==================================================================== */
/*  Main Page Component                                                  */
/* ==================================================================== */

export const FigmaSyncPage: React.FC = () => {
  const { t } = useDesignLab();
  const data = useFigmaSyncData();
  const statusCfg = STATUS_CONFIG[data.syncStatus];

  return (
    <div className="flex flex-col mx-auto max-w-5xl gap-6 pb-16">
      {/* Page Header */}
      <div>
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-action-primary/10 text-action-primary">
            <Figma className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <Text as="h1" className="text-xl font-bold text-text-primary">
                Figma Token Sync
              </Text>
              <DataProvenanceBadge level="derived" />
            </div>
            <Text variant="secondary" className="text-sm">
              Monitor design token synchronization between Figma and code
            </Text>
            <Text variant="secondary" className="text-[10px] mt-0.5">
              Token envanteri türetilmiş · Figma API bağlantısı yapılandırılmamış
            </Text>
          </div>
        </div>
      </div>

      {/* Sync Status Banner */}
      <div className={["flex items-center gap-3 rounded-2xl border px-5 py-4", (data.syncStatus as string) === "synced" ? "border-state-success-text/20 bg-state-success-bg" : (data.syncStatus as string) === "never" ? "border-[var(--border-subtle)] bg-surface-muted" : (data.syncStatus as string) === "drift" ? "border-state-warning-text/20 bg-state-warning-bg" : "border-state-danger-text/20 bg-state-danger-bg"].join(" ")}>
        {statusCfg.icon}
        <div className="flex-1">
          <Text className="text-sm font-semibold text-text-primary">
            Token sync durumu: Figma API baglantisi yapilandirilmamis
          </Text>
          <Text variant="secondary" className="text-xs">
            Token dosyalari analiz ediliyor. {data.tokenSourceFiles} kaynak dosya, {data.cssCustomProperties} CSS custom property.
          </Text>
        </div>
      </div>

      {/* Stat Cards — derived from token build */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="CSS Custom Properties"
          value={data.totalTokens}
          icon={<Palette className="h-5 w-5" />}
          subtitle={`${data.tokenGroups.length + data.additionalCategories.length} kategoride`}
        />
        <StatCard
          label="Kullanan Bilesenler"
          value={data.componentCount}
          icon={<Layers className="h-5 w-5" />}
          subtitle="Token tuketicisi"
        />
        <StatCard
          label="Kaynak Dosya"
          value={data.tokenSourceFiles}
          icon={<Box className="h-5 w-5" />}
          subtitle="packages/design-system/src/tokens/"
        />
        <StatCard
          label="Figma Baglantisi"
          value="Veri yok"
          icon={<Figma className="h-5 w-5" />}
          subtitle="API yapilandirilmamis"
        />
      </div>

      {/* Token Categories + Diff Viewer grid */}
      <div className="grid gap-6 lg:grid-cols-[1fr_1.5fr]">
        {/* Token Categories */}
        <div className="rounded-2xl border border-border-subtle bg-surface-default p-5">
          <Text as="div" className="mb-4 text-sm font-semibold text-text-primary">
            Token Categories
          </Text>
          <div className="flex flex-col gap-1">
            {data.tokenGroups.map((group) => (
              <TokenCategoryRow
                key={group}
                name={group}
                count={data.tokenCounts[group]}
                total={data.totalTokens}
              />
            ))}
          </div>
        </div>

        {/* Drift Viewer — no data without Figma API */}
        <div className="rounded-2xl border border-border-subtle bg-surface-default">
          <div className="flex items-center justify-between border-b border-border-subtle px-5 py-3">
            <Text className="text-sm font-semibold text-text-primary">
              Token Drift
            </Text>
          </div>
          <div className="flex items-center justify-center py-12">
            <div className="text-center">
              <Clock className="mx-auto h-8 w-8 text-[var(--text-subtle)]" />
              <Text className="mt-2 text-sm font-medium text-text-primary">Veri Yok</Text>
              <Text variant="secondary" className="mt-1 text-xs">
                Figma API baglantisi yapilandirildiginda drift analizi burada gorunecek
              </Text>
            </div>
          </div>
        </div>
      </div>

      {/* Token Altyapi Ozeti — derived from repo */}
      <div className="rounded-2xl border border-border-subtle bg-surface-default p-5">
        <Text as="div" className="mb-3 text-sm font-semibold text-text-primary">
          Token Altyapi Ozeti
        </Text>
        <Text variant="secondary" className="text-xs">
          <code className="rounded-xs bg-surface-canvas px-1.5 py-0.5 text-[11px] font-mono">generate-theme-css.mjs --check</code> komutu ile token-CSS eslesmesi dogrulanabilir.
        </Text>
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          {[
            { label: "Token kaynak dosyalari", value: `${data.tokenSourceFiles} dosya` },
            { label: "Build ciktisi (tokens.json)", value: "Mevcut" },
            { label: "Ek kategoriler", value: data.additionalCategories.join(", ") },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-2 rounded-xl bg-surface-canvas px-3 py-2.5">
              <CheckCircle2 className="h-4 w-4 shrink-0 text-state-success-text" />
              <div>
                <Text className="text-xs font-medium text-text-primary">{item.label}</Text>
                <Text variant="secondary" className="text-[10px]">{item.value}</Text>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default FigmaSyncPage;
