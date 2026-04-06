/**
 * Leadership Proof Page
 *
 * Combines all evidence-backed leadership metrics in a single view:
 * 1. Quality badges section
 * 2. Benchmark results
 * 3. Compatibility matrix summary
 * 4. ROI Calculator
 * 5. Reference app links
 * 6. Release timeline
 * 7. Analytics summary
 */

import React, { useMemo, _useState } from "react";
import { Text } from "@mfe/design-system";
import {
  Trophy,
  Award,
  Zap,
  Shield,
  BookOpen,
  Tag,
  BarChart3,
  Calculator,
  ExternalLink,
  CheckCircle,
  ArrowRight,
} from "lucide-react";
import { useDesignLab } from "../DesignLabProvider";
import ReleaseTimelinePanel from "../intelligence/ReleaseTimelinePanel";
import ROICalculator from "../intelligence/ROICalculator";
import { useDesignLabAnalytics } from "../intelligence/useDesignLabAnalytics";

/* ------------------------------------------------------------------ */
/*  Badge data                                                          */
/* ------------------------------------------------------------------ */

/** Static badges whose values never change at runtime */
const STATIC_BADGES = [
  { label: "Tests", value: "5910 pass", color: "bg-state-success-text/10 text-state-success-text" },
  { label: "Coverage", value: "85%", color: "bg-state-success-text/10 text-state-success-text" },
  { label: "TypeScript", value: "strict", color: "bg-action-primary/10 text-action-primary" },
  { label: "Bundle", value: "gated", color: "bg-state-success-text/10 text-state-success-text" },
  { label: "A11y", value: "axe-core", color: "bg-action-primary/10 text-action-primary" },
  { label: "Tokens", value: "DTCG", color: "bg-state-warning-text/10 text-state-warning-text" },
  { label: "Node", value: "20 | 22", color: "bg-state-success-text/10 text-state-success-text" },
  { label: "React", value: "18.2 | 18.3", color: "bg-action-primary/10 text-action-primary" },
];

/** Build the full badges array with dynamic counts derived from the catalog index */
function buildBadges(index: { items: unknown[]; summary?: { exported?: number } }) {
  const componentCount = index.summary?.exported ?? index.items.length;
  const storyCount = index.items.filter(
    (item) => (item as { demoMode?: string }).demoMode === "live" || (item as { demoMode?: string }).demoMode === "inspector",
  ).length || index.items.length;

  return [
    STATIC_BADGES[0],
    STATIC_BADGES[1],
    STATIC_BADGES[2],
    { label: "Components", value: String(componentCount), color: "bg-action-primary/10 text-action-primary" },
    { label: "Stories", value: String(storyCount), color: "bg-action-primary/10 text-action-primary" },
    ...STATIC_BADGES.slice(3),
  ];
}

/* ------------------------------------------------------------------ */
/*  Compatibility matrix summary                                        */
/* ------------------------------------------------------------------ */

const COMPAT_ROWS = [
  { category: "React 18.2 + Node 20", status: "certified" as const },
  { category: "React 18.2 + Node 22", status: "certified" as const },
  { category: "React 18.3 + Node 20", status: "certified" as const },
  { category: "React 18.3 + Node 22", status: "certified" as const },
  { category: "Webpack 5 (5.100+)", status: "certified" as const },
  { category: "Vite 5.x", status: "certified" as const },
  { category: "Next.js 14", status: "certified" as const },
  { category: "AG Grid 34.3.1", status: "certified" as const },
  { category: "Module Federation (6 remotes)", status: "certified" as const },
];

/* ------------------------------------------------------------------ */
/*  Reference apps                                                      */
/* ------------------------------------------------------------------ */

const REFERENCE_APPS = [
  {
    name: "Dashboard Demo",
    description: "KPI cards, charts, activity feed",
    template: "dashboard",
    components: ["Card", "LineChart", "BarChart", "PieChart", "ChartContainer"],
    timeToValue: "< 10 min",
  },
  {
    name: "CRUD Demo",
    description: "List + detail + create/edit forms",
    template: "crud",
    components: ["DataGrid", "FormBuilder", "Dialog", "Button"],
    timeToValue: "< 15 min",
  },
  {
    name: "Admin Demo",
    description: "Settings + user management",
    template: "admin",
    components: ["Tabs", "Switch", "DataGrid", "Avatar", "usePermission"],
    timeToValue: "< 15 min",
  },
];

/* ------------------------------------------------------------------ */
/*  Section wrapper                                                     */
/* ------------------------------------------------------------------ */

function Section({
  id,
  icon,
  iconBg,
  title,
  subtitle,
  children,
}: {
  id: string;
  icon: React.ReactNode;
  iconBg: string;
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${iconBg}`}>
          {icon}
        </div>
        <div>
          <Text className="text-lg font-semibold text-text-primary">{title}</Text>
          <Text variant="secondary" className="text-xs">{subtitle}</Text>
        </div>
      </div>
      {children}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/*  Main component                                                      */
/* ------------------------------------------------------------------ */

export default function LeadershipProofPage() {
  const { index } = useDesignLab();
  const badges = useMemo(() => buildBadges(index), [index]);
  const analytics = useDesignLabAnalytics();

  const topViewed = analytics.getTopViewed(5);
  const topSearched = analytics.getTopSearched(5);
  const engagement = analytics.getEngagement();

  return (
    <div className="flex flex-col gap-10 pb-12">
      {/* ── Hero ── */}
      <div className="relative overflow-hidden rounded-3xl bg-linear-to-br from-state-warning-text/5 via-surface-default to-action-primary/5 px-6 py-10 sm:px-10 sm:py-14">
        <div className="pointer-events-none absolute inset-0 opacity-[0.02]"
          style={{
            backgroundImage: "radial-gradient(circle, currentColor 1px, transparent 1px)",
            backgroundSize: "24px 24px",
          }}
        />
        <div className="relative text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-state-warning-text/10">
            <Trophy className="h-8 w-8 text-state-warning-text" />
          </div>
          <Text as="div" className="text-3xl font-extrabold tracking-tight text-text-primary sm:text-4xl">
            Leadership Proof
          </Text>
          <Text variant="secondary" className="mx-auto mt-3 max-w-2xl text-base leading-7">
            Tekrarlanabilir kanıtlar, referans uygulamalar ve platform güvenilirlik altyapısı
          </Text>
        </div>
      </div>

      {/* ── 1. Quality Badges ── */}
      <Section
        id="badges"
        icon={<Award className="h-5 w-5 text-state-warning-text" />}
        iconBg="bg-state-warning-text/10"
        title="Quality Badges"
        subtitle="Platform kalite göstergeleri"
      >
        <div className="flex flex-wrap gap-2">
          {badges.map((badge) => (
            <span
              key={badge.label}
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold ${badge.color}`}
            >
              <CheckCircle className="h-3 w-3" />
              {badge.label}: {badge.value}
            </span>
          ))}
        </div>
      </Section>

      {/* ── 2. Benchmark Results ── */}
      <Section
        id="benchmarks"
        icon={<Zap className="h-5 w-5 text-state-warning-text" />}
        iconBg="bg-state-warning-text/10"
        title="Benchmark Results"
        subtitle="Tekrarlanabilir performans ölçümleri"
      >
        <div className="rounded-xl border border-border-subtle bg-surface-default p-5">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="text-center">
              <Text className="text-2xl font-extrabold tabular-nums text-text-primary">6</Text>
              <Text variant="secondary" className="text-xs">Paket benchmarked</Text>
            </div>
            <div className="text-center">
              <Text className="text-2xl font-extrabold tabular-nums text-state-success-text">CI</Text>
              <Text variant="secondary" className="text-xs">Otomatik regresyon tespiti</Text>
            </div>
            <div className="text-center">
              <Text className="text-2xl font-extrabold tabular-nums text-text-primary">JSON</Text>
              <Text variant="secondary" className="text-xs">Versiyonlu sonuçlar</Text>
            </div>
          </div>
          <Text variant="secondary" className="mt-4 text-xs">
            Benchmark suite: <code className="rounded-xs bg-surface-canvas px-1.5 py-0.5 text-[11px]">pnpm --filter @mfe/benchmarks bench</code>
          </Text>
        </div>
      </Section>

      {/* ── 3. Compatibility Matrix ── */}
      <Section
        id="compatibility"
        icon={<Shield className="h-5 w-5 text-action-primary" />}
        iconBg="bg-action-primary/10"
        title="Certified Compatibility"
        subtitle="CI matrix ile doğrulanmış platform kombinasyonları"
      >
        <div className="grid gap-2 sm:grid-cols-3">
          {COMPAT_ROWS.map((row) => (
            <div
              key={row.category}
              className="flex items-center gap-2 rounded-lg border border-border-subtle bg-surface-default px-3 py-2"
            >
              <CheckCircle className="h-4 w-4 shrink-0 text-state-success-text" />
              <Text className="text-xs font-medium text-text-primary">{row.category}</Text>
            </div>
          ))}
        </div>
      </Section>

      {/* ── 4. ROI Calculator ── */}
      <div id="roi">
        <ROICalculator />
      </div>

      {/* ── 5. Reference Apps ── */}
      <Section
        id="reference-apps"
        icon={<BookOpen className="h-5 w-5 text-action-primary" />}
        iconBg="bg-action-primary/10"
        title="Reference Applications"
        subtitle="Hemen başlayabileceğiniz şablon uygulamalar"
      >
        <div className="grid gap-4 sm:grid-cols-3">
          {REFERENCE_APPS.map((app) => (
            <div
              key={app.template}
              className="group rounded-2xl border border-border-subtle bg-surface-default p-5 transition hover:border-border-default hover:shadow-md"
            >
              <Text className="text-sm font-semibold text-text-primary">{app.name}</Text>
              <Text variant="secondary" className="mt-1 text-xs">{app.description}</Text>
              <div className="mt-3 flex flex-wrap gap-1">
                {app.components.map((c) => (
                  <span
                    key={c}
                    className="rounded-xs bg-surface-canvas px-1.5 py-0.5 text-[10px] font-medium text-text-secondary"
                  >
                    {c}
                  </span>
                ))}
              </div>
              <div className="mt-3 flex items-center justify-between">
                <Text variant="secondary" className="text-[11px]">
                  First value: {app.timeToValue}
                </Text>
                <ArrowRight className="h-3.5 w-3.5 text-text-secondary opacity-0 transition group-hover:opacity-100" />
              </div>
              <code className="mt-2 block rounded-xs bg-surface-canvas px-2 py-1 text-[10px] text-text-secondary">
                npx @mfe/create-app my-app --template {app.template}
              </code>
            </div>
          ))}
        </div>
      </Section>

      {/* ── 6. Release Timeline ── */}
      <div id="releases">
        <ReleaseTimelinePanel />
      </div>

      {/* ── 7. Analytics Summary ── */}
      <Section
        id="analytics"
        icon={<BarChart3 className="h-5 w-5 text-state-info-text" />}
        iconBg="bg-state-info-text/10"
        title="Usage Analytics"
        subtitle="Design Lab kullanım istatistikleri"
      >
        <div className="grid gap-4 sm:grid-cols-3">
          <div className="rounded-xl border border-border-subtle bg-surface-default p-4 text-center">
            <Text className="text-2xl font-extrabold tabular-nums text-text-primary">
              {engagement.totalViews}
            </Text>
            <Text variant="secondary" className="text-xs">Toplam Görüntülenme</Text>
          </div>
          <div className="rounded-xl border border-border-subtle bg-surface-default p-4 text-center">
            <Text className="text-2xl font-extrabold tabular-nums text-text-primary">
              {engagement.uniqueComponents}
            </Text>
            <Text variant="secondary" className="text-xs">Benzersiz Bileşen</Text>
          </div>
          <div className="rounded-xl border border-border-subtle bg-surface-default p-4 text-center">
            <Text className="text-2xl font-extrabold tabular-nums text-text-primary">
              {engagement.avgTimeMs > 0 ? `${Math.round(engagement.avgTimeMs / 1000)}s` : "-"}
            </Text>
            <Text variant="secondary" className="text-xs">Ort. Zaman / Sayfa</Text>
          </div>
        </div>

        {topViewed.length > 0 && (
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div className="rounded-xl border border-border-subtle bg-surface-default p-4">
              <Text className="mb-3 text-xs font-semibold text-text-secondary">En Çok Görüntülenen</Text>
              {topViewed.map((item, i) => (
                <div key={item.name} className="flex items-center justify-between py-1">
                  <Text className="text-xs text-text-primary">
                    <span className="mr-2 text-text-secondary">{i + 1}.</span>
                    {item.name}
                  </Text>
                  <Text variant="secondary" className="text-xs tabular-nums">{item.views}</Text>
                </div>
              ))}
            </div>
            {topSearched.length > 0 && (
              <div className="rounded-xl border border-border-subtle bg-surface-default p-4">
                <Text className="mb-3 text-xs font-semibold text-text-secondary">En Çok Aranan</Text>
                {topSearched.map((item, i) => (
                  <div key={item.query} className="flex items-center justify-between py-1">
                    <Text className="text-xs text-text-primary">
                      <span className="mr-2 text-text-secondary">{i + 1}.</span>
                      {item.query}
                    </Text>
                    <Text variant="secondary" className="text-xs tabular-nums">{item.count}</Text>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </Section>
    </div>
  );
}
