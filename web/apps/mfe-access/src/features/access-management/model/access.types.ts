export type AccessLevel = 'NONE' | 'VIEW' | 'MANAGE';

export interface AccessModulePolicy {
  moduleKey: string;
  moduleLabel: string;
  level: AccessLevel;
  lastUpdatedAt: string;
  updatedBy: string;
}

export interface AccessRole {
  id: string;
  name: string;
  description?: string;
  memberCount: number;
  isSystemRole?: boolean;
  policies: AccessModulePolicy[];
  lastModifiedAt: string;
  lastModifiedBy: string;
  permissions?: string[];
}

export interface AccessFilters {
  search: string;
  moduleKey: string;
  level: AccessLevel | 'ALL';
}
