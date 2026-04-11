export type AuditFeedCapabilityId =
  | "auth.session.created"
  | "user.session-timeout.synced"
  | "user.session-timeout.conflict"
  | "user.notification-preference.synced"
  | "user.notification-preference.conflict"
  | "user.locale.synced"
  | "user.locale.conflict"
  | "user.timezone.synced"
  | "user.timezone.conflict"
  | "user.date-format.synced"
  | "user.date-format.conflict"
  | "user.time-format.synced"
  | "user.time-format.conflict";

export type AuditSummaryGroupId =
  | "auth.session"
  | "profile.session-timeout"
  | "profile.notification-preference"
  | "profile.locale"
  | "profile.timezone"
  | "profile.date-format"
  | "profile.time-format";

export type OfflineMutationKind =
  | "profile.sync"
  | "notification.preference.sync"
  | "profile.locale.sync"
  | "profile.timezone.sync"
  | "profile.date-format.sync"
  | "profile.time-format.sync"
  | (string & {});
export type OfflineMutationConflictPolicy = "manual" | "client-wins" | "server-wins";
export type OfflineMutationCapabilityId =
  | "generic.offline-mutation"
  | "profile.session-timeout.sync"
  | "profile.notification-preference.sync"
  | "profile.locale.sync"
  | "profile.timezone.sync"
  | "profile.date-format.sync"
  | "profile.time-format.sync";

export type SharedReportFilterKey = "search" | "status" | "level" | "department" | "location" | "gender" | "employmentType" | "collarType" | "education" | "company" | "month";
export type ReportExportMode = "none" | "download" | "job";

export type AuditFeedCapability = {
  id: AuditFeedCapabilityId;
  action: string;
  description: string;
  routeLabel: string;
  service: string;
  shortcutLabel: string;
  shortcutTitle: string;
};

export type AuditSummaryGroup = {
  id: AuditSummaryGroupId;
  title: string;
  description: string;
  primaryCapabilityId: AuditFeedCapabilityId;
  capabilityIds: readonly AuditFeedCapabilityId[];
  metricLabels: Partial<Record<AuditFeedCapabilityId, string>>;
};

export type AuditCapabilitySummarySnapshot = {
  capabilityId: AuditFeedCapabilityId;
  total: number;
  latestEventId: string | null;
  latestEventTimestamp: string | null;
  latestAction: string | null;
};

export type AuditSummaryMetric = {
  capabilityId: AuditFeedCapabilityId;
  label: string;
  total: number;
};

export type AuditSummarySnapshot = {
  groupId: AuditSummaryGroupId;
  title: string;
  description: string;
  total: number;
  latestEventId: string | null;
  latestEventTimestamp: string | null;
  latestCapabilityId: AuditFeedCapabilityId | null;
  metrics: AuditSummaryMetric[];
};

export type AuditFeedNotificationDescriptor = {
  id: string;
  message: string;
  description: string;
  type: "success" | "warning";
  priority: "normal" | "high";
  open: boolean;
  pathname: string;
  search: string;
  actionLabel: string;
  source: string;
};

export type AuditFeedNotificationPolicy = {
  capabilityId: AuditFeedCapabilityId;
  kind: "success" | "conflict";
  source: string;
};

export type OfflineMutationPolicyDescriptor = {
  capabilityId: OfflineMutationCapabilityId;
  kind: OfflineMutationKind;
  title: string;
  description: string;
  auditAction: string;
  retryPolicyKey: string;
  retryDelayMs: number;
  conflictPolicy: OfflineMutationConflictPolicy;
  successAuditCapabilityId: AuditFeedCapabilityId;
  conflictAuditCapabilityId: AuditFeedCapabilityId;
};

export type SharedReportId = "users-overview" | "roles-access" | "audit-activity" | "hr-demografik-yapi" | "monthly-login-summary" | "weekly-audit-digest" | "hr-compensation";

export type SharedReportCatalogItem = {
  id: SharedReportId;
  title: string;
  description: string;
  permissionCode: string;
  exportPermissionCode?: string | null;
  metricLabel: string;
  emptyMessage: string;
  supportedChannels: readonly ReportChannel[];
  dataModeByChannel: Partial<Record<ReportChannel, ReportDataMode>>;
  favoriteChannels: readonly ReportChannel[];
  savedFilterChannels: readonly ReportChannel[];
  exportModeByChannel: Partial<Record<ReportChannel, ReportExportMode>>;
  filterParity: readonly SharedReportFilterDescriptor[];
  webRouteSegment: string;
  webRoute: string;
  webModuleId: string;
  /** Sidebar category for grouping (e.g., "Periyodik", "İnsan Kaynakları") */
  category?: string;
  /** Classification tags (e.g., ["periodic", "monthly"]) */
  tags?: readonly string[];
  /** Report presentation type */
  type?: "grid" | "dashboard" | "mixed";
  /** Icon for sidebar/hub display */
  icon?: string;
  /** OpenFGA report group key for authorization (e.g., "HR_REPORTS") */
  reportGroup?: string;
};

export type ReportChannel = "web" | "mobile";
export type ReportDataMode = "live" | "mock";

export type SharedReportFilterDescriptor = {
  key: SharedReportFilterKey;
  label: string;
  supportedChannels: readonly ReportChannel[];
};

export type SharedReportSavedFilter = {
  id: string;
  reportId: SharedReportId;
  channel: ReportChannel;
  name: string;
  values: Record<string, unknown>;
  createdAt: string;
};

export type SharedReportPreferenceSnapshot = {
  favorites: SharedReportId[];
  savedFilters: SharedReportSavedFilter[];
};

export const SHARED_REPORT_FAVORITES_GRID_ID = "reports.catalog.preferences";
export const SHARED_REPORT_FAVORITES_VARIANT_NAME = "favorite-reports";

const AUDIT_FEED_CAPABILITIES: readonly AuditFeedCapability[] = [
  {
    id: "auth.session.created",
    action: "SESSION_CREATED",
    description: "Open SESSION_CREATED records in the central audit feed.",
    routeLabel: "auth-service / SESSION_CREATED",
    service: "auth-service",
    shortcutLabel: "Session Audit",
    shortcutTitle: "Open SESSION_CREATED audit records for this user",
  },
  {
    id: "user.session-timeout.synced",
    action: "USER_SESSION_TIMEOUT_SYNCED",
    description: "Open successful session-timeout replay records in the central audit feed.",
    routeLabel: "user-service / USER_SESSION_TIMEOUT_SYNCED",
    service: "user-service",
    shortcutLabel: "Replay Audit",
    shortcutTitle: "Open USER_SESSION_TIMEOUT_SYNCED audit records for this user",
  },
  {
    id: "user.session-timeout.conflict",
    action: "USER_SESSION_TIMEOUT_SYNC_CONFLICT",
    description: "Open replay conflict records in the central audit feed.",
    routeLabel: "user-service / USER_SESSION_TIMEOUT_SYNC_CONFLICT",
    service: "user-service",
    shortcutLabel: "Replay Conflict",
    shortcutTitle: "Open USER_SESSION_TIMEOUT_SYNC_CONFLICT audit records for this user",
  },
  {
    id: "user.notification-preference.synced",
    action: "USER_NOTIFICATION_PREFERENCE_SYNCED",
    description: "Open successful notification-preference replay records in the central audit feed.",
    routeLabel: "user-service / USER_NOTIFICATION_PREFERENCE_SYNCED",
    service: "user-service",
    shortcutLabel: "Preference Audit",
    shortcutTitle: "Open USER_NOTIFICATION_PREFERENCE_SYNCED audit records for this user",
  },
  {
    id: "user.notification-preference.conflict",
    action: "USER_NOTIFICATION_PREFERENCE_SYNC_CONFLICT",
    description: "Open notification-preference replay conflict records in the central audit feed.",
    routeLabel: "user-service / USER_NOTIFICATION_PREFERENCE_SYNC_CONFLICT",
    service: "user-service",
    shortcutLabel: "Preference Conflict",
    shortcutTitle: "Open USER_NOTIFICATION_PREFERENCE_SYNC_CONFLICT audit records for this user",
  },
  {
    id: "user.locale.synced",
    action: "USER_LOCALE_SYNCED",
    description: "Open successful locale replay records in the central audit feed.",
    routeLabel: "user-service / USER_LOCALE_SYNCED",
    service: "user-service",
    shortcutLabel: "Locale Audit",
    shortcutTitle: "Open USER_LOCALE_SYNCED audit records for this user",
  },
  {
    id: "user.locale.conflict",
    action: "USER_LOCALE_SYNC_CONFLICT",
    description: "Open locale replay conflict records in the central audit feed.",
    routeLabel: "user-service / USER_LOCALE_SYNC_CONFLICT",
    service: "user-service",
    shortcutLabel: "Locale Conflict",
    shortcutTitle: "Open USER_LOCALE_SYNC_CONFLICT audit records for this user",
  },
  {
    id: "user.timezone.synced",
    action: "USER_TIMEZONE_SYNCED",
    description: "Open successful timezone replay records in the central audit feed.",
    routeLabel: "user-service / USER_TIMEZONE_SYNCED",
    service: "user-service",
    shortcutLabel: "Timezone Audit",
    shortcutTitle: "Open USER_TIMEZONE_SYNCED audit records for this user",
  },
  {
    id: "user.timezone.conflict",
    action: "USER_TIMEZONE_SYNC_CONFLICT",
    description: "Open timezone replay conflict records in the central audit feed.",
    routeLabel: "user-service / USER_TIMEZONE_SYNC_CONFLICT",
    service: "user-service",
    shortcutLabel: "Timezone Conflict",
    shortcutTitle: "Open USER_TIMEZONE_SYNC_CONFLICT audit records for this user",
  },
  {
    id: "user.date-format.synced",
    action: "USER_DATE_FORMAT_SYNCED",
    description: "Open successful date-format replay records in the central audit feed.",
    routeLabel: "user-service / USER_DATE_FORMAT_SYNCED",
    service: "user-service",
    shortcutLabel: "Date Format Audit",
    shortcutTitle: "Open USER_DATE_FORMAT_SYNCED audit records for this user",
  },
  {
    id: "user.date-format.conflict",
    action: "USER_DATE_FORMAT_SYNC_CONFLICT",
    description: "Open date-format replay conflict records in the central audit feed.",
    routeLabel: "user-service / USER_DATE_FORMAT_SYNC_CONFLICT",
    service: "user-service",
    shortcutLabel: "Date Format Conflict",
    shortcutTitle: "Open USER_DATE_FORMAT_SYNC_CONFLICT audit records for this user",
  },
  {
    id: "user.time-format.synced",
    action: "USER_TIME_FORMAT_SYNCED",
    description: "Open successful time-format replay records in the central audit feed.",
    routeLabel: "user-service / USER_TIME_FORMAT_SYNCED",
    service: "user-service",
    shortcutLabel: "Time Format Audit",
    shortcutTitle: "Open USER_TIME_FORMAT_SYNCED audit records for this user",
  },
  {
    id: "user.time-format.conflict",
    action: "USER_TIME_FORMAT_SYNC_CONFLICT",
    description: "Open time-format replay conflict records in the central audit feed.",
    routeLabel: "user-service / USER_TIME_FORMAT_SYNC_CONFLICT",
    service: "user-service",
    shortcutLabel: "Time Format Conflict",
    shortcutTitle: "Open USER_TIME_FORMAT_SYNC_CONFLICT audit records for this user",
  },
] as const;

const SHARED_REPORT_CATALOG: readonly SharedReportCatalogItem[] = [
  {
    id: "users-overview",
    title: "Kullanici raporu",
    description: "Kullanici hacmi, son girisler ve rol dagilimi icin hizli ozet.",
    permissionCode: "user-read",
    exportPermissionCode: null,
    metricLabel: "Toplam kullanici",
    emptyMessage: "Kullanici raporu icin gosterilecek kayit bulunamadi.",
    supportedChannels: ["web", "mobile"],
    dataModeByChannel: {
      web: "live",
      mobile: "live",
    },
    favoriteChannels: ["web", "mobile"],
    savedFilterChannels: ["web", "mobile"],
    exportModeByChannel: {
      web: "none",
      mobile: "none",
    },
    filterParity: [
      { key: "search", label: "Arama", supportedChannels: ["web", "mobile"] },
      { key: "status", label: "Durum", supportedChannels: ["web", "mobile"] },
    ],
    webRouteSegment: "users",
    webRoute: "/admin/reports/users",
    webModuleId: "reports.users",
    category: "Genel",
  
    reportGroup: "HR_REPORTS",
  },
  {
    id: "roles-access",
    title: "Erisim rolleri",
    description: "Rol havuzu, uye yogunlugu ve yetki yukunu mobilde takip et.",
    permissionCode: "access-read",
    exportPermissionCode: null,
    metricLabel: "Toplam rol",
    emptyMessage: "Erisim rolleri raporu icin kayit bulunamadi.",
    supportedChannels: ["web", "mobile"],
    dataModeByChannel: {
      web: "live",
      mobile: "live",
    },
    favoriteChannels: ["web", "mobile"],
    savedFilterChannels: ["web", "mobile"],
    exportModeByChannel: {
      web: "none",
      mobile: "none",
    },
    filterParity: [{ key: "search", label: "Arama", supportedChannels: ["web", "mobile"] }],
    webRouteSegment: "access",
    webRoute: "/admin/reports/access",
    webModuleId: "reports.access",
    category: "Erişim & Güvenlik",
  
    reportGroup: "ANALYTICS_REPORTS",
  },
  {
    id: "audit-activity",
    title: "Audit aktivitesi",
    description: "Son olaylar, seviye dagilimi ve servis hareketlerini izle.",
    permissionCode: "audit-read",
    exportPermissionCode: "audit-export",
    metricLabel: "Toplam audit olayi",
    emptyMessage: "Audit aktivitesi icin gosterilecek olay bulunamadi.",
    supportedChannels: ["web", "mobile"],
    dataModeByChannel: {
      web: "live",
      mobile: "live",
    },
    favoriteChannels: ["web", "mobile"],
    savedFilterChannels: ["web", "mobile"],
    exportModeByChannel: {
      web: "job",
      mobile: "none",
    },
    filterParity: [
      { key: "search", label: "Arama", supportedChannels: ["web", "mobile"] },
      { key: "level", label: "Seviye", supportedChannels: ["web", "mobile"] },
    ],
    webRouteSegment: "audit",
    webRoute: "/admin/reports/audit",
    webModuleId: "reports.audit",
    category: "Denetim",
  
    reportGroup: "ANALYTICS_REPORTS",
  },
  {
    id: "hr-demografik-yapi",
    title: "IK demografik yapi",
    description: "Cinsiyet, yas, egitim, kidem ve cesitlilik metrikleriyle insan kaynaklari demografik raporu.",
    permissionCode: "hr-read",
    exportPermissionCode: null,
    metricLabel: "Toplam calisan",
    emptyMessage: "IK demografik raporu icin gosterilecek kayit bulunamadi.",
    supportedChannels: ["web"],
    dataModeByChannel: {
      web: "mock",
    },
    favoriteChannels: ["web"],
    savedFilterChannels: ["web"],
    exportModeByChannel: {
      web: "none",
    },
    filterParity: [
      { key: "search", label: "Arama", supportedChannels: ["web"] },
      { key: "department", label: "Departman", supportedChannels: ["web"] },
      { key: "location", label: "Lokasyon", supportedChannels: ["web"] },
      { key: "gender", label: "Cinsiyet", supportedChannels: ["web"] },
      { key: "employmentType", label: "Istihdam Turu", supportedChannels: ["web"] },
    ],
    webRouteSegment: "hr-demografik-yapi",
    webRoute: "/admin/reports/hr-demografik-yapi",
    webModuleId: "reports.hr-demographic",
    category: "İnsan Kaynakları",
  
    reportGroup: "HR_REPORTS",
  },
  {
    id: "monthly-login-summary",
    title: "Aylık giriş özeti",
    description: "Her ay otomatik oluşturulan kullanıcı giriş istatistikleri raporu.",
    permissionCode: "user-read",
    exportPermissionCode: null,
    metricLabel: "Toplam giriş",
    emptyMessage: "Aylık giriş özeti için gösterilecek kayıt bulunamadı.",
    supportedChannels: ["web"],
    dataModeByChannel: { web: "live" },
    favoriteChannels: ["web"],
    savedFilterChannels: ["web"],
    exportModeByChannel: { web: "none" },
    filterParity: [
      { key: "search", label: "Arama", supportedChannels: ["web"] },
    ],
    webRouteSegment: "monthly-login-summary",
    webRoute: "/admin/reports/monthly-login-summary",
    webModuleId: "reports.monthly-login-summary",
    category: "Periyodik",
    tags: ["periodic", "monthly"],
    icon: "📅",
  
    reportGroup: "ANALYTICS_REPORTS",
  },
  {
    id: "weekly-audit-digest",
    title: "Haftalık denetim özeti",
    description: "Her hafta otomatik derlenen denetim olayları ve güvenlik uyarıları.",
    permissionCode: "audit-read",
    exportPermissionCode: null,
    metricLabel: "Toplam olay",
    emptyMessage: "Haftalık denetim özeti için gösterilecek kayıt bulunamadı.",
    supportedChannels: ["web"],
    dataModeByChannel: { web: "live" },
    favoriteChannels: ["web"],
    savedFilterChannels: ["web"],
    exportModeByChannel: { web: "none" },
    filterParity: [
      { key: "search", label: "Arama", supportedChannels: ["web"] },
      { key: "level", label: "Seviye", supportedChannels: ["web"] },
    ],
    webRouteSegment: "weekly-audit-digest",
    webRoute: "/admin/reports/weekly-audit-digest",
    webModuleId: "reports.weekly-audit-digest",
    category: "Periyodik",
    tags: ["periodic", "weekly"],
    icon: "📋",
  
    reportGroup: "ANALYTICS_REPORTS",
  },
  {
    id: "hr-compensation",
    title: "Ücret ve Yan Haklar Analitiği",
    description: "Mercer/WTW standardında kapsamlı ücretlendirme analizi — iç denge, cinsiyet eşitliği, yüzdelik dağılımlar, trend.",
    permissionCode: "hr-read",
    exportPermissionCode: "hr-export",
    metricLabel: "Toplam bordro",
    emptyMessage: "Ücret analitiği için gösterilecek veri bulunamadı.",
    supportedChannels: ["web"],
    dataModeByChannel: { web: "live" },
    favoriteChannels: ["web"],
    savedFilterChannels: ["web"],
    exportModeByChannel: { web: "job" },
    filterParity: [
      { key: "search", label: "Arama", supportedChannels: ["web"] },
      { key: "department", label: "Departman", supportedChannels: ["web"] },
      { key: "collarType", label: "Yaka Tipi", supportedChannels: ["web"] },
      { key: "gender", label: "Cinsiyet", supportedChannels: ["web"] },
      { key: "education", label: "Eğitim", supportedChannels: ["web"] },
    ],
    webRouteSegment: "hr-compensation",
    webRoute: "/admin/reports/hr-compensation",
    webModuleId: "reports.hr-compensation",
    category: "İnsan Kaynakları",
    type: "mixed",
    icon: "💰",
  
    reportGroup: "HR_REPORTS",
  },
] as const;

const AUDIT_SUMMARY_GROUPS: readonly AuditSummaryGroup[] = [
  {
    id: "auth.session",
    title: "Session bootstrap",
    description: "Track central audit visibility for auth session creation before drilling into the protected route.",
    primaryCapabilityId: "auth.session.created",
    capabilityIds: ["auth.session.created"],
    metricLabels: {
      "auth.session.created": "Session events",
    },
  },
  {
    id: "profile.session-timeout",
    title: "Session-timeout replay",
    description: "Surface replay success and conflict totals for queued session-timeout mutations.",
    primaryCapabilityId: "user.session-timeout.synced",
    capabilityIds: ["user.session-timeout.synced", "user.session-timeout.conflict"],
    metricLabels: {
      "user.session-timeout.synced": "Replay success",
      "user.session-timeout.conflict": "Replay conflict",
    },
  },
  {
    id: "profile.notification-preference",
    title: "Notification preference replay",
    description: "Surface replay success and conflict totals for queued notification preference mutations.",
    primaryCapabilityId: "user.notification-preference.synced",
    capabilityIds: ["user.notification-preference.synced", "user.notification-preference.conflict"],
    metricLabels: {
      "user.notification-preference.synced": "Preference success",
      "user.notification-preference.conflict": "Preference conflict",
    },
  },
  {
    id: "profile.locale",
    title: "Locale replay",
    description: "Surface replay success and conflict totals for queued locale mutations.",
    primaryCapabilityId: "user.locale.synced",
    capabilityIds: ["user.locale.synced", "user.locale.conflict"],
    metricLabels: {
      "user.locale.synced": "Locale success",
      "user.locale.conflict": "Locale conflict",
    },
  },
  {
    id: "profile.timezone",
    title: "Timezone replay",
    description: "Surface replay success and conflict totals for queued timezone mutations.",
    primaryCapabilityId: "user.timezone.synced",
    capabilityIds: ["user.timezone.synced", "user.timezone.conflict"],
    metricLabels: {
      "user.timezone.synced": "Timezone success",
      "user.timezone.conflict": "Timezone conflict",
    },
  },
  {
    id: "profile.date-format",
    title: "Date-format replay",
    description: "Surface replay success and conflict totals for queued date-format mutations.",
    primaryCapabilityId: "user.date-format.synced",
    capabilityIds: ["user.date-format.synced", "user.date-format.conflict"],
    metricLabels: {
      "user.date-format.synced": "Date format success",
      "user.date-format.conflict": "Date format conflict",
    },
  },
  {
    id: "profile.time-format",
    title: "Time-format replay",
    description: "Surface replay success and conflict totals for queued time-format mutations.",
    primaryCapabilityId: "user.time-format.synced",
    capabilityIds: ["user.time-format.synced", "user.time-format.conflict"],
    metricLabels: {
      "user.time-format.synced": "Time format success",
      "user.time-format.conflict": "Time format conflict",
    },
  },
] as const;

const AUDIT_FEED_NOTIFICATION_POLICIES: readonly AuditFeedNotificationPolicy[] = [
  {
    capabilityId: "user.session-timeout.synced",
    kind: "success",
    source: "audit.summary.profile.session-timeout",
  },
  {
    capabilityId: "user.session-timeout.conflict",
    kind: "conflict",
    source: "audit.summary.profile.session-timeout",
  },
  {
    capabilityId: "user.notification-preference.synced",
    kind: "success",
    source: "audit.summary.profile.notification-preference",
  },
  {
    capabilityId: "user.notification-preference.conflict",
    kind: "conflict",
    source: "audit.summary.profile.notification-preference",
  },
  {
    capabilityId: "user.locale.synced",
    kind: "success",
    source: "audit.summary.profile.locale",
  },
  {
    capabilityId: "user.locale.conflict",
    kind: "conflict",
    source: "audit.summary.profile.locale",
  },
  {
    capabilityId: "user.timezone.synced",
    kind: "success",
    source: "audit.summary.profile.timezone",
  },
  {
    capabilityId: "user.timezone.conflict",
    kind: "conflict",
    source: "audit.summary.profile.timezone",
  },
  {
    capabilityId: "user.date-format.synced",
    kind: "success",
    source: "audit.summary.profile.date-format",
  },
  {
    capabilityId: "user.date-format.conflict",
    kind: "conflict",
    source: "audit.summary.profile.date-format",
  },
  {
    capabilityId: "user.time-format.synced",
    kind: "success",
    source: "audit.summary.profile.time-format",
  },
  {
    capabilityId: "user.time-format.conflict",
    kind: "conflict",
    source: "audit.summary.profile.time-format",
  },
] as const;

const OFFLINE_MUTATION_POLICIES: readonly OfflineMutationPolicyDescriptor[] = [
  {
    capabilityId: "profile.session-timeout.sync",
    kind: "profile.sync",
    title: "Profile session-timeout sync",
    description: "Replay queued profile session-timeout writes with optimistic locking and audit coverage.",
    auditAction: "USER_SESSION_TIMEOUT_SYNC_REQUESTED",
    retryPolicyKey: "profile.sync.standard",
    retryDelayMs: 30_000,
    conflictPolicy: "client-wins",
    successAuditCapabilityId: "user.session-timeout.synced",
    conflictAuditCapabilityId: "user.session-timeout.conflict",
  },
  {
    capabilityId: "profile.notification-preference.sync",
    kind: "notification.preference.sync",
    title: "Notification preference sync",
    description: "Replay queued notification-preference writes with optimistic locking and audit coverage.",
    auditAction: "USER_NOTIFICATION_PREFERENCE_SYNC_REQUESTED",
    retryPolicyKey: "notification.preference.standard",
    retryDelayMs: 30_000,
    conflictPolicy: "client-wins",
    successAuditCapabilityId: "user.notification-preference.synced",
    conflictAuditCapabilityId: "user.notification-preference.conflict",
  },
  {
    capabilityId: "profile.locale.sync",
    kind: "profile.locale.sync",
    title: "Profile locale sync",
    description: "Replay queued locale writes with optimistic locking and audit coverage.",
    auditAction: "USER_LOCALE_SYNC_REQUESTED",
    retryPolicyKey: "profile.locale.standard",
    retryDelayMs: 30_000,
    conflictPolicy: "client-wins",
    successAuditCapabilityId: "user.locale.synced",
    conflictAuditCapabilityId: "user.locale.conflict",
  },
  {
    capabilityId: "profile.timezone.sync",
    kind: "profile.timezone.sync",
    title: "Profile timezone sync",
    description: "Replay queued timezone writes with optimistic locking and audit coverage.",
    auditAction: "USER_TIMEZONE_SYNC_REQUESTED",
    retryPolicyKey: "profile.timezone.standard",
    retryDelayMs: 30_000,
    conflictPolicy: "client-wins",
    successAuditCapabilityId: "user.timezone.synced",
    conflictAuditCapabilityId: "user.timezone.conflict",
  },
  {
    capabilityId: "profile.date-format.sync",
    kind: "profile.date-format.sync",
    title: "Profile date-format sync",
    description: "Replay queued date-format writes with optimistic locking and audit coverage.",
    auditAction: "USER_DATE_FORMAT_SYNC_REQUESTED",
    retryPolicyKey: "profile.date-format.standard",
    retryDelayMs: 30_000,
    conflictPolicy: "client-wins",
    successAuditCapabilityId: "user.date-format.synced",
    conflictAuditCapabilityId: "user.date-format.conflict",
  },
  {
    capabilityId: "profile.time-format.sync",
    kind: "profile.time-format.sync",
    title: "Profile time-format sync",
    description: "Replay queued time-format writes with optimistic locking and audit coverage.",
    auditAction: "USER_TIME_FORMAT_SYNC_REQUESTED",
    retryPolicyKey: "profile.time-format.standard",
    retryDelayMs: 30_000,
    conflictPolicy: "client-wins",
    successAuditCapabilityId: "user.time-format.synced",
    conflictAuditCapabilityId: "user.time-format.conflict",
  },
] as const;

export function listAuditFeedCapabilities() {
  return [...AUDIT_FEED_CAPABILITIES];
}

export function getAuditFeedCapability(capabilityId: AuditFeedCapabilityId): AuditFeedCapability {
  const match = AUDIT_FEED_CAPABILITIES.find((capability) => capability.id === capabilityId);
  if (!match) {
    throw new Error(`Unknown audit capability: ${capabilityId}`);
  }
  return match;
}

export function buildAuditFeedSearch(capabilityId: AuditFeedCapabilityId, email: string): string {
  const capability = getAuditFeedCapability(capabilityId);
  const normalizedEmail = email.trim().toLowerCase();
  const search = new URLSearchParams({
    service: capability.service,
    action: capability.action,
  });
  if (!normalizedEmail) {
    return search.toString();
  }
  return search.toString();
}

export function listAuditSummaryGroups() {
  return [...AUDIT_SUMMARY_GROUPS];
}

export function getAuditSummaryGroup(groupId: AuditSummaryGroupId): AuditSummaryGroup {
  const match = AUDIT_SUMMARY_GROUPS.find((group) => group.id === groupId);
  if (!match) {
    throw new Error(`Unknown audit summary group: ${groupId}`);
  }
  return match;
}

export function listAuditSummaryGroupCapabilities(
  groupId: AuditSummaryGroupId,
): AuditFeedCapability[] {
  const group = getAuditSummaryGroup(groupId);
  return group.capabilityIds.map((capabilityId) => getAuditFeedCapability(capabilityId));
}

const normalizeSnapshot = (
  capabilityId: AuditFeedCapabilityId,
  snapshots: readonly AuditCapabilitySummarySnapshot[],
): AuditCapabilitySummarySnapshot => {
  return (
    snapshots.find((snapshot) => snapshot.capabilityId === capabilityId) ?? {
      capabilityId,
      total: 0,
      latestEventId: null,
      latestEventTimestamp: null,
      latestAction: null,
    }
  );
};

const resolveLatestSnapshot = (
  snapshots: readonly AuditCapabilitySummarySnapshot[],
): AuditCapabilitySummarySnapshot | null => {
  let current: AuditCapabilitySummarySnapshot | null = null;

  for (const snapshot of snapshots) {
    if (!snapshot.latestEventTimestamp) {
      continue;
    }
    if (!current || !current.latestEventTimestamp) {
      current = snapshot;
      continue;
    }
    if (Date.parse(snapshot.latestEventTimestamp) > Date.parse(current.latestEventTimestamp)) {
      current = snapshot;
    }
  }

  return current;
};

export function buildAuditSummarySnapshot(
  groupId: AuditSummaryGroupId,
  snapshots: readonly AuditCapabilitySummarySnapshot[],
): AuditSummarySnapshot {
  const group = getAuditSummaryGroup(groupId);
  const relevantSnapshots = group.capabilityIds.map((capabilityId) =>
    normalizeSnapshot(capabilityId, snapshots),
  );
  const latestSnapshot = resolveLatestSnapshot(relevantSnapshots);

  return {
    groupId: group.id,
    title: group.title,
    description: group.description,
    total: relevantSnapshots.reduce((sum, snapshot) => sum + snapshot.total, 0),
    latestEventId: latestSnapshot?.latestEventId ?? null,
    latestEventTimestamp: latestSnapshot?.latestEventTimestamp ?? null,
    latestCapabilityId: latestSnapshot?.capabilityId ?? null,
    metrics: relevantSnapshots.map((snapshot) => ({
      capabilityId: snapshot.capabilityId,
      label:
        group.metricLabels[snapshot.capabilityId] ??
        getAuditFeedCapability(snapshot.capabilityId).shortcutLabel,
      total: snapshot.total,
    })),
  };
}

export function getAuditFeedNotificationPolicy(
  capabilityId: AuditFeedCapabilityId,
): AuditFeedNotificationPolicy | null {
  return (
    AUDIT_FEED_NOTIFICATION_POLICIES.find((policy) => policy.capabilityId === capabilityId) ?? null
  );
}

export function buildAuditFeedNotificationDescriptor(
  capabilityId: AuditFeedCapabilityId,
  email: string,
  delta: number,
  total: number,
): AuditFeedNotificationDescriptor | null {
  const policy = getAuditFeedNotificationPolicy(capabilityId);
  if (!policy) {
    return null;
  }

  const normalizedEmail = email.trim().toLowerCase();
  if (!normalizedEmail) {
    return null;
  }

  const capability = getAuditFeedCapability(capabilityId);
  const noun = delta === 1 ? "yeni kayıt" : "yeni kayıt";

  if (policy.kind === "conflict") {
    return {
      id: `audit-summary-${capabilityId}-${normalizedEmail}-${total}`,
      message:
        capabilityId === "user.session-timeout.conflict"
          ? "Session-timeout replay conflict algılandı"
          : capabilityId === "user.notification-preference.conflict"
            ? "Notification preference replay conflict algılandı"
            : capabilityId === "user.locale.conflict"
              ? "Locale replay conflict algılandı"
              : capabilityId === "user.date-format.conflict"
                ? "Date-format replay conflict algılandı"
                : capabilityId === "user.time-format.conflict"
                  ? "Time-format replay conflict algılandı"
                  : "Timezone replay conflict algılandı",
      description: `${delta} ${noun} audit feed'e eklendi. Görünür toplam conflict sayısı ${total}.`,
      type: "warning",
      priority: "high",
      open: true,
      pathname: "/audit/events",
      search: buildAuditFeedSearch(capabilityId, normalizedEmail),
      actionLabel: capability.shortcutLabel,
      source: policy.source,
    };
  }

  return {
    id: `audit-summary-${capabilityId}-${normalizedEmail}-${total}`,
    message:
      capabilityId === "user.session-timeout.synced"
        ? "Session-timeout replay kaydı güncellendi"
        : capabilityId === "user.notification-preference.synced"
          ? "Notification preference replay kaydı güncellendi"
          : capabilityId === "user.locale.synced"
            ? "Locale replay kaydı güncellendi"
            : capabilityId === "user.date-format.synced"
              ? "Date-format replay kaydı güncellendi"
              : capabilityId === "user.time-format.synced"
                ? "Time-format replay kaydı güncellendi"
                : "Timezone replay kaydı güncellendi",
    description: `${delta} ${noun} audit feed'de görünür oldu. Görünür toplam success sayısı ${total}.`,
    type: "success",
    priority: "normal",
    open: false,
    pathname: "/audit/events",
    search: buildAuditFeedSearch(capabilityId, normalizedEmail),
    actionLabel: capability.shortcutLabel,
    source: policy.source,
  };
}

export function listOfflineMutationPolicies() {
  return [...OFFLINE_MUTATION_POLICIES];
}

export function getOfflineMutationPolicy(
  kind: OfflineMutationKind,
): OfflineMutationPolicyDescriptor | null {
  return OFFLINE_MUTATION_POLICIES.find((policy) => policy.kind === kind) ?? null;
}

export function buildDefaultOfflineMutationPolicy(
  kind: OfflineMutationKind,
): OfflineMutationPolicyDescriptor {
  return {
    capabilityId: "generic.offline-mutation",
    kind,
    title: `${kind} mutation`,
    description: "Fallback policy for queued writes that have not been promoted into the shared capability catalog yet.",
    auditAction: "OFFLINE_MUTATION_REQUESTED",
    retryPolicyKey: `${kind}.standard`,
    retryDelayMs: 30_000,
    conflictPolicy: "manual",
    successAuditCapabilityId: "user.session-timeout.synced",
    conflictAuditCapabilityId: "user.session-timeout.conflict",
  };
}

export function getOfflineMutationPolicyByCapabilityId(
  capabilityId: OfflineMutationCapabilityId,
): OfflineMutationPolicyDescriptor {
  const match = OFFLINE_MUTATION_POLICIES.find((policy) => policy.capabilityId === capabilityId);
  if (!match) {
    throw new Error(`Unknown offline mutation capability: ${capabilityId}`);
  }
  return match;
}

export function listSharedReports() {
  return [...SHARED_REPORT_CATALOG];
}

export function getSharedReport(reportId: SharedReportId) {
  const report = SHARED_REPORT_CATALOG.find((item) => item.id === reportId);
  if (!report) {
    throw new Error(`Unknown shared report: ${reportId}`);
  }

  return report;
}

export function listSharedReportsForChannel(channel: ReportChannel) {
  return SHARED_REPORT_CATALOG.filter((item) => item.supportedChannels.includes(channel));
}

export function getSharedReportByWebModuleId(webModuleId: string) {
  const report = SHARED_REPORT_CATALOG.find((item) => item.webModuleId === webModuleId);
  if (!report) {
    throw new Error(`Unknown shared web report module: ${webModuleId}`);
  }

  return report;
}

export function getSharedReportDataMode(
  reportId: SharedReportId,
  channel: ReportChannel,
): ReportDataMode | null {
  return getSharedReport(reportId).dataModeByChannel[channel] ?? null;
}

export function getSharedReportExportMode(
  reportId: SharedReportId,
  channel: ReportChannel,
): ReportExportMode {
  return getSharedReport(reportId).exportModeByChannel[channel] ?? "none";
}

export function listSharedReportFilters(reportId: SharedReportId) {
  return [...getSharedReport(reportId).filterParity];
}

export function listSharedReportFiltersForChannel(
  reportId: SharedReportId,
  channel: ReportChannel,
) {
  return listSharedReportFilters(reportId).filter((item) => item.supportedChannels.includes(channel));
}

export function supportsSharedReportFavorites(reportId: SharedReportId, channel: ReportChannel) {
  return getSharedReport(reportId).favoriteChannels.includes(channel);
}

export function supportsSharedReportSavedFilters(reportId: SharedReportId, channel: ReportChannel) {
  return getSharedReport(reportId).savedFilterChannels.includes(channel);
}

export function isSharedReportId(value: unknown): value is SharedReportId {
  return typeof value === "string" && SHARED_REPORT_CATALOG.some((item) => item.id === value);
}

export function normalizeSharedReportIds(values: unknown): SharedReportId[] {
  if (!Array.isArray(values)) {
    return [];
  }

  return values.filter((item): item is SharedReportId => isSharedReportId(item));
}

export function buildSharedReportSavedFilterGridId(
  reportId: SharedReportId,
  channel: ReportChannel,
) {
  return `reports.saved-filters.${channel}.${reportId}`;
}

export function buildSharedReportFavoritesVariantState(
  favorites: readonly SharedReportId[],
): Record<string, unknown> {
  return {
    filterModel: {
      favorites: normalizeSharedReportIds([...favorites]),
    },
  };
}

export function readSharedReportFavoritesFromVariantState(state: unknown): SharedReportId[] {
  if (!state || typeof state !== "object") {
    return [];
  }

  const filterModel = (state as { filterModel?: unknown }).filterModel;
  if (!filterModel || typeof filterModel !== "object") {
    return [];
  }

  return normalizeSharedReportIds((filterModel as { favorites?: unknown }).favorites);
}

export function buildSharedReportSavedFilterVariantState(
  values: Record<string, unknown>,
): Record<string, unknown> {
  return {
    filterModel: { ...values },
  };
}

export function readSharedReportSavedFilterValuesFromVariantState(
  state: unknown,
): Record<string, unknown> {
  if (!state || typeof state !== "object") {
    return {};
  }

  const filterModel = (state as { filterModel?: unknown }).filterModel;
  if (!filterModel || typeof filterModel !== "object" || Array.isArray(filterModel)) {
    return {};
  }

  return { ...(filterModel as Record<string, unknown>) };
}

export function createEmptySharedReportPreferenceSnapshot(): SharedReportPreferenceSnapshot {
  return {
    favorites: [],
    savedFilters: [],
  };
}

export function isSharedReportFavorite(
  snapshot: SharedReportPreferenceSnapshot,
  reportId: SharedReportId,
) {
  return snapshot.favorites.includes(reportId);
}

export function toggleSharedReportFavorite(
  snapshot: SharedReportPreferenceSnapshot,
  reportId: SharedReportId,
): SharedReportPreferenceSnapshot {
  const favorites = snapshot.favorites.includes(reportId)
    ? snapshot.favorites.filter((item) => item !== reportId)
    : [...snapshot.favorites, reportId];

  return {
    favorites,
    savedFilters: [...snapshot.savedFilters],
  };
}

export function listSharedReportSavedFilters(
  snapshot: SharedReportPreferenceSnapshot,
  reportId: SharedReportId,
  channel: ReportChannel,
) {
  return snapshot.savedFilters.filter(
    (item) => item.reportId === reportId && item.channel === channel,
  );
}

export function saveSharedReportFilter(
  snapshot: SharedReportPreferenceSnapshot,
  filter: SharedReportSavedFilter,
  maxPerReport = 5,
): SharedReportPreferenceSnapshot {
  const scopedExisting = snapshot.savedFilters.filter(
    (item) =>
      item.reportId === filter.reportId &&
      item.channel === filter.channel &&
      item.id !== filter.id,
  );
  const otherReports = snapshot.savedFilters.filter(
    (item) => item.reportId !== filter.reportId || item.channel !== filter.channel,
  );
  const scopedNext = [filter, ...scopedExisting].slice(0, maxPerReport);

  return {
    favorites: [...snapshot.favorites],
    savedFilters: [...otherReports, ...scopedNext],
  };
}

export function removeSharedReportSavedFilter(
  snapshot: SharedReportPreferenceSnapshot,
  presetId: string,
): SharedReportPreferenceSnapshot {
  return {
    favorites: [...snapshot.favorites],
    savedFilters: snapshot.savedFilters.filter((item) => item.id !== presetId),
  };
}
