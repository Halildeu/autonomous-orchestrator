# Design System Catalog Status

> Generated: 2026-04-07 | Source: adoption-report + grep analysis
> Updates: Re-run `npm run doctor` to verify current status

## Lifecycle Definitions

| Status | Meaning | Test Expectation | Maintenance |
|--------|---------|-----------------|-------------|
| **ACTIVE** | Used in production apps | Full test suite | High priority |
| **SHOWCASE** | Design Lab catalog demo, planned for adoption | Contract + depth tests | Medium priority |
| **EXPERIMENTAL** | Not stable, API may change | Contract tests only | Low priority |
| **DEPRECATED** | Scheduled for removal | None — freeze | None |

---

## Enterprise Components (41)

All enterprise components currently have **0 production imports**. They exist in the Design Lab catalog for demonstration and future adoption.

### SHOWCASE — Planned for Adoption

These components are stable, well-tested (contract+depth), and ready for production use when the relevant feature is built.

| Component | Category | Storybook | Readiness |
|-----------|----------|-----------|-----------|
| DataExportDialog | UX Pattern | Yes | Ready — awaiting reporting export feature |
| DateRangePicker | UX Pattern | Yes | Ready — awaiting dashboard date filters |
| EmptyStateBuilder | UX Pattern | Yes | Ready — generic utility |
| ExecutiveKPIStrip | KPI/Metrics | Yes | Ready — awaiting executive dashboard |
| FileUploadZone | UX Pattern | Yes | Ready — awaiting file management feature |
| FilterPresets | UX Pattern | Yes | Ready — awaiting saved filter feature |
| InlineEdit | UX Pattern | Yes | Ready — awaiting inline editing feature |
| NotificationCenter | UX Pattern | Yes | Ready — awaiting notification hub feature |
| CommentThread | Collaboration | Yes | Ready — awaiting discussion feature |
| ActivityFeed | Collaboration | Yes | Ready — awaiting activity log feature |
| StatusTimeline | Timeline | Yes | Ready — awaiting status history feature |

### EXPERIMENTAL — Stable But Niche

Domain-specific components for specialized use cases. May need API refinement before production.

| Component | Category | Notes |
|-----------|----------|-------|
| ComparisonTable | Analytics | Nested row expansion, toggle groups |
| DecisionMatrix | Decision Support | Weighted scoring grid |
| FineKinney | Risk | Quantitative risk assessment (OHS domain) |
| GanttTimeline | Project | Timeline with dependencies |
| GovernanceBoard | Governance | Control/compliance dashboard |
| MetricComparisonCard | KPI/Metrics | Side-by-side metric widget |
| OrgChart | Organizational | SVG hierarchy chart |
| PivotTable | Analytics | Dynamic pivot grid |
| ProcessFlow | Workflow | Step-by-step flow visualization |
| RiskMatrix | Risk | 2D probability x impact grid |
| SWOTMatrix | Strategy | 4-quadrant SWOT analysis |
| TrainingTracker | HR | Certification/training progress |
| ValueStream | Lean | Value stream mapping |
| FlowBuilder | Workflow | Visual node/edge flow editor |
| ApprovalWorkflow | Workflow | Step-based approval chain |

### EXPERIMENTAL — Chart Components (ECharts-backed)

Built on ECharts engine. Available in Design Lab but not yet imported by any production app.

| Component | Chart Type | Notes |
|-----------|-----------|-------|
| AgingBuckets | Stacked Bar | Receivables aging visualization |
| BoxPlot | Statistical | Quartile distribution |
| BulletChart | Progress | Single-metric bullet |
| ControlChart | Statistical | SPC control limits |
| FunnelChart | Funnel | Conversion funnel (horizontal+vertical) |
| GaugeChart | Gauge | Progress gauge with thresholds |
| HeatmapCalendar | Heatmap | GitHub-style day heatmap |
| HistogramChart | Statistical | Frequency distribution |
| MicroChart | Sparkline | Inline mini visualization |
| ParetoChart | Statistical | 80/20 pareto analysis |
| RadarChart | Radar | Multi-dimensional comparison |
| SankeyDiagram | Flow | Sankey flow diagram |
| TreemapChart | Hierarchy | Treemap visualization |
| WaterfallChart | Financial | Cumulative waterfall |

### Theme Utility

| Component | Status | Notes |
|-----------|--------|-------|
| ThemeLayout | SHOWCASE | Layout container with theme toggle — Design Lab internal |

---

## Advanced Packages (x-*)

| Package | Production Usage | Status | Notes |
|---------|-----------------|--------|-------|
| **x-charts** | 12 files (mfe-shell, mfe-reporting) | **ACTIVE** | ECharts wrapper, BarChart + PieChart used |
| **x-data-grid** | 0 files | **EXPERIMENTAL** | Apps use AgGridServer wrapper directly instead |
| **x-form-builder** | 0 files | **DEPRECATED** | Superseded by `design-system/form` (React Hook Form + Zod) |
| **x-editor** | 0 files | **EXPERIMENTAL** | Tiptap v2 wrapper, awaiting rich-text feature |
| **x-kanban** | 0 files | **EXPERIMENTAL** | dnd-kit kanban, awaiting project management feature |
| **x-scheduler** | 0 files | **EXPERIMENTAL** | Calendar scheduler, awaiting scheduling feature |

---

## Production-Active Components (Top 30 by Import Count)

For reference — these are the components that matter most for quality investment.

| Component | Imports | Package |
|-----------|---------|---------|
| Text | 125 | primitives |
| Button | 46 | primitives |
| Badge | 42 | primitives |
| MenuBar | 27 | components |
| ColumnMeta | 19 | advanced/data-grid |
| Pagination | 17 | components |
| Descriptions | 16 | components |
| PageLayout | 15 | patterns |
| Card/CardHeader/CardBody | 14 | primitives |
| Tabs | 13 | components |
| TableSimple | 12 | components |
| Select | 11 | primitives |
| IconButton | 10 | primitives |
| SummaryStrip | 10 | patterns |
| Input/TextInput | 9 | primitives |
| FilterBar | 9 | patterns |
| SearchFilterListing | 8 | components |
| EntityGridTemplate | 7 | advanced/data-grid |
| Tooltip | 7 | primitives |
| Tag | 7 | primitives |

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-07 | 41 enterprise components classified SHOWCASE/EXPERIMENTAL | 0 production imports; maintain for catalog, defer testing investment |
| 2026-04-07 | x-form-builder marked DEPRECATED | Superseded by design-system/form (RHF + Zod) |
| 2026-04-07 | x-data-grid marked EXPERIMENTAL | Apps use AgGridServer wrapper, not this package |
| 2026-04-07 | Test investment prioritized for ACTIVE components only | Doctor-driven: fix real issues, not inflate metrics for unused code |
