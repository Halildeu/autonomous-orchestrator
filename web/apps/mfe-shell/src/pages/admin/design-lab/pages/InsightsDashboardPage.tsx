import React, { useMemo, useState } from "react";
import {
  Activity,
  TrendingUp,
  TrendingDown,
  FileQuestion,
  BarChart3,
  ArrowUpRight,
  ArrowDownRight,
  Minus,
  AlertCircle,
} from "lucide-react";
import { Text } from "@mfe/design-system";
import { AdoptionHeatmap } from "../insights/AdoptionHeatmap";
import {
  getAdoptionData,
  getMostUsed,
  getLeastUsed,
  getUndocumentedBacklog,
  getAdoptionRate,
  deriveConsumerApps,
} from "../insights/insightsUtils";
import { useDesignLab } from "../DesignLabProvider";
import { DataProvenanceBadge } from "../components/DataProvenanceBadge";

/* ------------------------------------------------------------------ */
/*  InsightsDashboardPage — Component adoption metrics & trends        */
/*                                                                     */
/*  Derived from real doc entry whereUsed data.                        */
/*  No simulated/mock data — adoption is calculated from actual usage. */
/* ------------------------------------------------------------------ */

type ViewMode = "heatmap" | "table";

const STATUS_ICON: Record<string, React.ReactNode> = {
  adopted: <ArrowUpRight className="h-3.5 w-3.5 text-state-success-text" />,
  unused: <Minus className="h-3.5 w-3.5 text-[var(--text-subtle)]" />,
};

const STATUS_BADGE: Record<string, string> = {
  adopted: "bg-state-success-bg text-state-success-text",
  unused: "bg-[var(--surface-muted)] text-[var(--text-secondary)]",
};

export default function InsightsDashboardPage() {
  const { index, docEntryMap } = useDesignLab();
  const [viewMode, setViewMode] = useState<ViewMode>("heatmap");
  const [searchQuery, setSearchQuery] = useState("");

  const consumerApps = useMemo(() => deriveConsumerApps(index.items), [index]);
  const data = useMemo(() => getAdoptionData(index.items, docEntryMap, consumerApps), [index, docEntryMap, consumerApps]);
  const mostUsed = useMemo(() => getMostUsed(data), [data]);
  const leastUsed = useMemo(() => getLeastUsed(data), [data]);
  const backlog = useMemo(() => getUndocumentedBacklog(data), [data]);
  const adoptionRate = useMemo(() => getAdoptionRate(data), [data]);

  const documented = data.filter((d) => d.documented).length;

  const filtered = useMemo(() => {
    if (!searchQuery) return data;
    const q = searchQuery.toLowerCase();
    return data.filter((d) => d.component.toLowerCase().includes(q));
  }, [data, searchQuery]);

  return (
    <div className="flex flex-col mx-auto max-w-6xl gap-6 p-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-linear-to-br from-action-primary/20 to-action-primary/20">
          <Activity className="h-5 w-5 text-action-primary" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <Text as="h1" className="text-xl font-bold text-text-primary">Adoption Insights</Text>
            <DataProvenanceBadge level="derived" />
          </div>
          <Text variant="secondary" className="text-sm">
            {data.length} bilesen, {consumerApps.length} tuketici uygulamada izleniyor (whereUsed verisinden)
          </Text>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          label="Toplam Bilesen"
          value={data.length}
          icon={<BarChart3 className="h-4 w-4 text-action-primary" />}
          color="bg-action-primary/10"
        />
        <SummaryCard
          label="Dokumante"
          value={`${documented}/${data.length}`}
          sub={`${data.length > 0 ? Math.round((documented / data.length) * 100) : 0}%`}
          icon={<FileQuestion className="h-4 w-4 text-state-warning-text" />}
          color="bg-state-warning-bg"
        />
        <SummaryCard
          label="Kullanilan"
          value={data.filter((d) => d.status === "adopted").length}
          sub={`${adoptionRate}% benimseme`}
          icon={<TrendingUp className="h-4 w-4 text-state-success-text" />}
          color="bg-state-success-bg"
        />
        <SummaryCard
          label="Kullanilmayan"
          value={data.filter((d) => d.status === "unused").length}
          sub="whereUsed bos"
          icon={<Activity className="h-4 w-4 text-action-primary" />}
          color="bg-action-primary/10"
        />
      </div>

      {/* Heatmap / Table toggle + search */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex gap-1">
          {(["heatmap", "table"] as ViewMode[]).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => setViewMode(mode)}
              className={[
                "rounded-lg px-3 py-1.5 text-xs font-medium transition",
                viewMode === mode
                  ? "bg-action-primary text-text-inverse"
                  : "bg-surface-muted text-text-secondary hover:text-text-primary",
              ].join(" ")}
            >
              {mode === "heatmap" ? "Heatmap" : "Table"}
            </button>
          ))}
        </div>
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Bilesen filtrele..."
          className="rounded-lg border border-border-subtle bg-surface-default px-3 py-1.5 text-xs outline-hidden focus:border-action-primary"
        />
      </div>

      {/* Main Content */}
      {viewMode === "heatmap" ? (
        <div className="overflow-x-auto rounded-2xl border border-border-subtle bg-surface-default p-4">
          <AdoptionHeatmap data={filtered} consumerApps={consumerApps} />
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-border-subtle">
          <table className="w-full">
            <thead>
              <tr className="bg-surface-canvas text-[10px] font-semibold uppercase tracking-wider text-text-tertiary">
                <th className="px-4 py-3 text-left">Bilesen</th>
                <th className="px-3 py-3 text-center">Uygulamalar</th>
                <th className="px-3 py-3 text-center">Durum</th>
                <th className="px-3 py-3 text-center">Dokumante</th>
                <th className="px-3 py-3 text-center">Oncelik</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((entry) => (
                <tr key={entry.component} className="border-t border-border-subtle hover:bg-surface-muted/30 transition">
                  <td className="px-4 py-2.5">
                    <Text className="text-xs font-medium text-text-primary">{entry.component}</Text>
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <Text className="text-xs text-text-secondary">
                      {entry.whereUsedCount}/{consumerApps.length}
                    </Text>
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <span className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-semibold ${STATUS_BADGE[entry.status]}`}>
                      {STATUS_ICON[entry.status]} {entry.status === "adopted" ? "Kullaniliyor" : "Kullanilmiyor"}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    {entry.documented ? (
                      <span className="inline-block h-2 w-2 rounded-full bg-state-success-text" />
                    ) : (
                      <span className="inline-block h-2 w-2 rounded-full bg-state-danger-text" />
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <PriorityBar value={entry.priority} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Bottom panels: Most Used, Least Used, Backlog */}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Most Used */}
        <div className="rounded-2xl border border-border-subtle bg-surface-default p-4">
          <div className="mb-3 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-state-success-text" />
            <Text as="h3" className="text-sm font-semibold text-text-primary">En Cok Kullanilan</Text>
          </div>
          <div className="flex flex-col gap-2">
            {mostUsed.map((entry) => (
              <div key={entry.component} className="flex items-center justify-between rounded-lg bg-surface-canvas px-3 py-2">
                <Text className="text-xs font-medium text-text-primary">{entry.component}</Text>
                <Text className="text-xs text-text-secondary">{entry.whereUsedCount} uygulama</Text>
              </div>
            ))}
            {mostUsed.length === 0 && (
              <Text variant="secondary" className="text-xs">Veri yok</Text>
            )}
          </div>
        </div>

        {/* Least Used */}
        <div className="rounded-2xl border border-border-subtle bg-surface-default p-4">
          <div className="mb-3 flex items-center gap-2">
            <TrendingDown className="h-4 w-4 text-state-danger-text" />
            <Text as="h3" className="text-sm font-semibold text-text-primary">Kullanilmayan</Text>
          </div>
          <div className="flex flex-col gap-2">
            {leastUsed.map((entry) => (
              <div key={entry.component} className="flex items-center justify-between rounded-lg bg-surface-canvas px-3 py-2">
                <Text className="text-xs font-medium text-text-primary">{entry.component}</Text>
                <Text className="text-xs text-text-tertiary">whereUsed: 0</Text>
              </div>
            ))}
            {leastUsed.length === 0 && (
              <Text variant="secondary" className="text-xs">Tum bilesenler en az 1 yerde kullaniliyor</Text>
            )}
          </div>
        </div>

        {/* Undocumented Backlog */}
        <div className="rounded-2xl border border-border-subtle bg-surface-default p-4">
          <div className="mb-3 flex items-center gap-2">
            <AlertCircle className="h-4 w-4 text-state-warning-text" />
            <Text as="h3" className="text-sm font-semibold text-text-primary">Dokumante Edilmemis</Text>
            <span className="ml-auto rounded-full bg-state-warning-bg px-2 py-0.5 text-[10px] font-bold text-state-warning-text">
              {backlog.length}
            </span>
          </div>
          <div className="flex flex-col gap-2">
            {backlog.slice(0, 6).map((entry) => (
              <div key={entry.component} className="flex items-center justify-between rounded-lg bg-surface-canvas px-3 py-2">
                <div>
                  <Text className="text-xs font-medium text-text-primary">{entry.component}</Text>
                  <Text variant="secondary" className="text-[10px]">
                    {entry.whereUsedCount} uygulama
                  </Text>
                </div>
                <PriorityBar value={entry.priority} />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---- Sub-components ---- */

function SummaryCard({
  label,
  value,
  sub,
  icon,
  color,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div className="rounded-2xl border border-border-subtle bg-surface-default p-4">
      <div className="mb-2 flex items-center gap-2">
        <div className={`flex h-7 w-7 items-center justify-center rounded-lg ${color}`}>{icon}</div>
        <Text variant="secondary" className="text-[11px] font-medium">{label}</Text>
      </div>
      <div className="flex items-baseline gap-1.5">
        <Text as="div" className="text-2xl font-bold text-text-primary">{value}</Text>
        {sub && <Text variant="secondary" className="text-xs">{sub}</Text>}
      </div>
    </div>
  );
}

function PriorityBar({ value }: { value: number }) {
  const color = value >= 70 ? "bg-state-danger-text" : value >= 40 ? "bg-state-warning-text" : "bg-state-success-text";
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1.5 w-12 overflow-hidden rounded-full bg-surface-muted">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${value}%` }} />
      </div>
      <Text className="text-[10px] text-text-tertiary">{value}</Text>
    </div>
  );
}
