export type DynamicReportFilters = {
  search: string;
};

export type DynamicReportRow = Record<string, unknown>;

export type ReportColumnMeta = {
  field: string;
  headerName: string;
  type: 'text' | 'number' | 'date' | 'badge' | 'status' | 'currency' | 'boolean' | 'percent' | 'enum';
  width: number;
  sensitive: boolean;
  /** Badge/enum: raw value → variant color map (e.g., { ADMIN: 'danger', USER: 'info' }) */
  variantMap?: Record<string, string>;
  /** Badge/enum: raw value → i18n label key map */
  labelMap?: Record<string, string>;
  /** Status: raw value → { variant, labelKey } map */
  statusMap?: Record<string, { variant: string; labelKey: string }>;
  /** Currency: ISO 4217 code (default: 'TRY') */
  currencyCode?: string;
  /** Number/currency/percent: decimal places */
  decimals?: number;
  /** Number: suffix (e.g., 'dk', 'gün') */
  suffix?: string;
  /** Number: prefix (e.g., '₺') */
  prefix?: string;
};

export type ReportListItem = {
  key: string;
  title: string;
  description: string;
  category: string;
  /** CNS-006 R18: reportGroup from access_config for deny-default filtering */
  reportGroup?: string;
};

export type ReportMetadata = {
  key: string;
  title: string;
  description: string;
  category: string;
  columns: ReportColumnMeta[];
  defaultSort: string;
  defaultSortDirection: string;
};

export type ReportCategory = {
  name: string;
  count: number;
};
