/**
 * Release Timeline + Incident History
 *
 * Shows:
 * - Recent releases with version, date, changelog summary
 * - Known issues
 * - Incident history with resolution status
 * - Release health indicators
 *
 * Data from release-please manifest + governance audit trail
 */

import React, { _useMemo, useState } from "react";
import { Text } from "@mfe/design-system";
import {
  Tag,
  AlertTriangle,
  CheckCircle,
  Clock as _Clock,
  ChevronDown,
  ChevronRight,
  ExternalLink as _ExternalLink,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Types                                                               */
/* ------------------------------------------------------------------ */

interface ReleaseEntry {
  version: string;
  date: string;
  summary: string;
  health: "healthy" | "known-issues" | "incident";
  changes: number;
  breaking: number;
  knownIssues?: string[];
}

interface IncidentEntry {
  id: string;
  date: string;
  title: string;
  severity: "low" | "medium" | "high" | "critical";
  status: "open" | "investigating" | "resolved";
  resolution?: string;
  affectedVersions: string[];
}

/* ------------------------------------------------------------------ */
/*  Mock data — would be sourced from release-please + governance       */
/* ------------------------------------------------------------------ */

const RELEASES: ReleaseEntry[] = [
  {
    version: "3.12.0",
    date: "2026-03-20",
    summary: "AG Grid 34.3.1 upgrade, new ChartContainer component, x-scheduler improvements",
    health: "healthy",
    changes: 47,
    breaking: 0,
  },
  {
    version: "3.11.2",
    date: "2026-03-15",
    summary: "Hotfix: DataGrid column resize regression, FormBuilder validation edge case",
    health: "healthy",
    changes: 3,
    breaking: 0,
  },
  {
    version: "3.11.0",
    date: "2026-03-08",
    summary: "Design token DTCG migration, theme builder enhancements, new Badge variants",
    health: "known-issues",
    changes: 32,
    breaking: 1,
    knownIssues: ["Theme builder preview may flicker on Safari 17.2"],
  },
  {
    version: "3.10.0",
    date: "2026-02-28",
    summary: "x-editor collaboration mode, x-kanban swimlanes, performance improvements",
    health: "healthy",
    changes: 28,
    breaking: 0,
  },
];

const INCIDENTS: IncidentEntry[] = [
  {
    id: "INC-042",
    date: "2026-03-10",
    title: "Module Federation shared dependency negotiation failure on Node 22",
    severity: "high",
    status: "resolved",
    resolution: "Pinned webpack-module-federation to 0.8.4, added Node 22 to CI matrix",
    affectedVersions: ["3.11.0"],
  },
  {
    id: "INC-041",
    date: "2026-02-25",
    title: "x-data-grid SSRM export timeout on large datasets (>100k rows)",
    severity: "medium",
    status: "resolved",
    resolution: "Implemented chunked export with streaming, added configurable timeout",
    affectedVersions: ["3.9.0", "3.10.0"],
  },
];

/* ------------------------------------------------------------------ */
/*  Sub-components                                                      */
/* ------------------------------------------------------------------ */

const HEALTH_CONFIG = {
  healthy: { icon: CheckCircle, color: "text-state-success-text", bg: "bg-state-success-text/10", label: "Healthy" },
  "known-issues": { icon: AlertTriangle, color: "text-state-warning-text", bg: "bg-state-warning-text/10", label: "Known Issues" },
  incident: { icon: AlertTriangle, color: "text-state-danger-text", bg: "bg-state-danger-text/10", label: "Incident" },
} as const;

const SEVERITY_COLORS = {
  low: "bg-action-primary/10 text-action-primary",
  medium: "bg-state-warning-text/10 text-state-warning-text",
  high: "bg-state-warning-text/10 text-state-warning-text",
  critical: "bg-state-danger-text/10 text-state-danger-text",
} as const;

const STATUS_COLORS = {
  open: "bg-state-danger-text/10 text-state-danger-text",
  investigating: "bg-state-warning-text/10 text-state-warning-text",
  resolved: "bg-state-success-text/10 text-state-success-text",
} as const;

function ReleaseCard({ release }: { release: ReleaseEntry }) {
  const [expanded, setExpanded] = useState(false);
  const health = HEALTH_CONFIG[release.health];
  const HealthIcon = health.icon;

  return (
    <div className="relative flex gap-4">
      {/* Timeline dot + line */}
      <div className="flex flex-col items-center">
        <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${health.bg}`}>
          <HealthIcon className={`h-4 w-4 ${health.color}`} />
        </div>
        <div className="w-px flex-1 bg-border-subtle" />
      </div>

      {/* Content */}
      <div className="flex-1 pb-6">
        <button
          type="button"
          onClick={() => setExpanded(!expanded)}
          className="flex w-full items-start gap-3 text-left"
        >
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <Text className="text-sm font-semibold text-text-primary">v{release.version}</Text>
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${health.bg} ${health.color}`}>
                {health.label}
              </span>
              {release.breaking > 0 && (
                <span className="rounded-full bg-state-danger-text/10 px-2 py-0.5 text-[10px] font-medium text-state-danger-text">
                  {release.breaking} breaking
                </span>
              )}
            </div>
            <Text variant="secondary" className="mt-1 text-xs">
              {release.date} — {release.changes} changes
            </Text>
          </div>
          {expanded ? (
            <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-text-secondary" />
          ) : (
            <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-text-secondary" />
          )}
        </button>

        {expanded && (
          <div className="flex flex-col mt-3 gap-2 rounded-xl border border-border-subtle bg-surface-canvas p-4">
            <Text className="text-sm text-text-primary">{release.summary}</Text>
            {release.knownIssues && release.knownIssues.length > 0 && (
              <div className="mt-2">
                <Text className="text-xs font-semibold text-state-warning-text">Known Issues:</Text>
                <ul className="ml-4 mt-1 list-disc">
                  {release.knownIssues.map((issue, i) => (
                    <li key={i}>
                      <Text variant="secondary" className="text-xs">{issue}</Text>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function IncidentCard({ incident }: { incident: IncidentEntry }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <button
      type="button"
      onClick={() => setExpanded(!expanded)}
      className="w-full rounded-xl border border-border-subtle bg-surface-default p-4 text-left transition hover:border-border-default hover:shadow-xs"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className={`mt-0.5 h-4 w-4 shrink-0 ${SEVERITY_COLORS[incident.severity].split(" ")[1]}`} />
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <Text className="text-sm font-medium text-text-primary">{incident.id}</Text>
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${SEVERITY_COLORS[incident.severity]}`}>
              {incident.severity}
            </span>
            <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${STATUS_COLORS[incident.status]}`}>
              {incident.status}
            </span>
          </div>
          <Text className="mt-1 text-sm text-text-primary">{incident.title}</Text>
          <Text variant="secondary" className="mt-0.5 text-xs">
            {incident.date} — Affects: {incident.affectedVersions.join(", ")}
          </Text>

          {expanded && incident.resolution && (
            <div className="mt-3 rounded-lg border border-border-subtle bg-surface-canvas p-3">
              <Text className="text-xs font-semibold text-state-success-text">Resolution:</Text>
              <Text variant="secondary" className="mt-1 text-xs">{incident.resolution}</Text>
            </div>
          )}
        </div>
      </div>
    </button>
  );
}

/* ------------------------------------------------------------------ */
/*  Main component                                                      */
/* ------------------------------------------------------------------ */

export default function ReleaseTimelinePanel() {
  const [activeTab, setActiveTab] = useState<"releases" | "incidents">("releases");

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-action-primary/10">
          <Tag className="h-5 w-5 text-action-primary" />
        </div>
        <div>
          <Text className="text-lg font-semibold text-text-primary">Release Timeline</Text>
          <Text variant="secondary" className="text-xs">
            Sürüm geçmişi ve incident kayıtları
          </Text>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 rounded-xl border border-border-subtle bg-surface-canvas p-1">
        <button
          type="button"
          onClick={() => setActiveTab("releases")}
          className={[
            "flex-1 rounded-lg px-4 py-2 text-sm font-medium transition",
            activeTab === "releases"
              ? "bg-surface-default text-text-primary shadow-xs"
              : "text-text-secondary hover:text-text-primary",
          ].join(" ")}
        >
          <Tag className="mr-1.5 inline h-3.5 w-3.5" />
          Releases ({RELEASES.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("incidents")}
          className={[
            "flex-1 rounded-lg px-4 py-2 text-sm font-medium transition",
            activeTab === "incidents"
              ? "bg-surface-default text-text-primary shadow-xs"
              : "text-text-secondary hover:text-text-primary",
          ].join(" ")}
        >
          <AlertTriangle className="mr-1.5 inline h-3.5 w-3.5" />
          Incidents ({INCIDENTS.length})
        </button>
      </div>

      {/* Content */}
      {activeTab === "releases" ? (
        <div className="">
          {RELEASES.map((release) => (
            <ReleaseCard key={release.version} release={release} />
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {INCIDENTS.map((incident) => (
            <IncidentCard key={incident.id} incident={incident} />
          ))}
        </div>
      )}
    </div>
  );
}
