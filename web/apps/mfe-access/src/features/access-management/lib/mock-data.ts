import { AccessRole } from '../model/access.types';

export const mockAccessRoles: AccessRole[] = [
  {
    id: 'role-ops-admin',
    name: 'Operasyon Admin',
    description: 'Tüm modüllerde yönetim yetkisine sahip rol.',
    memberCount: 8,
    isSystemRole: true,
    lastModifiedAt: '2025-10-15T09:12:00Z',
    lastModifiedBy: 'melisa.erden',
    permissions: ['VIEW_USERS', 'MANAGE_USERS', 'VIEW_AUDIT', 'EDIT_SECURITY'],
    policies: [
      {
        moduleKey: 'USER_MANAGEMENT',
        moduleLabel: 'Kullanıcı Yönetimi',
        level: 'MANAGE',
        lastUpdatedAt: '2025-09-30T11:20:00Z',
        updatedBy: 'melisa.erden'
      },
      {
        moduleKey: 'SECURITY_CENTER',
        moduleLabel: 'Güvenlik Merkezi',
        level: 'MANAGE',
        lastUpdatedAt: '2025-09-11T08:43:00Z',
        updatedBy: 'selim.tas'
      },
      {
        moduleKey: 'AUDIT_TRAIL',
        moduleLabel: 'Audit Kayıtları',
        level: 'VIEW',
        lastUpdatedAt: '2025-10-02T10:05:00Z',
        updatedBy: 'melisa.erden'
      }
    ]
  },
  {
    id: 'role-warehouse',
    name: 'Depo Sorumlusu',
    description: 'Depo operasyonları ve stok yönetimi için rol.',
    memberCount: 24,
    lastModifiedAt: '2025-10-05T07:15:00Z',
    lastModifiedBy: 'ahmet.kara',
    permissions: ['MANAGE_WAREHOUSE', 'VIEW_PURCHASE'],
    policies: [
      {
        moduleKey: 'WAREHOUSE',
        moduleLabel: 'Depo Yönetimi',
        level: 'MANAGE',
        lastUpdatedAt: '2025-08-30T12:00:00Z',
        updatedBy: 'ahmet.kara'
      },
      {
        moduleKey: 'PURCHASE',
        moduleLabel: 'Satın Alma',
        level: 'VIEW',
        lastUpdatedAt: '2025-09-18T14:25:00Z',
        updatedBy: 'sema.ozturk'
      }
    ]
  },
  {
    id: 'role-support',
    name: 'Destek Uzmanı',
    description: 'Kullanıcı destek kayıtlarını görüntüleyebilir ve güncelleyebilir.',
    memberCount: 12,
    lastModifiedAt: '2025-09-27T16:48:00Z',
    lastModifiedBy: 'sema.ozturk',
    permissions: ['EDIT_USERS', 'VIEW_AUDIT'],
    policies: [
      {
        moduleKey: 'USER_MANAGEMENT',
        moduleLabel: 'Kullanıcı Yönetimi',
        level: 'MANAGE',
        lastUpdatedAt: '2025-09-26T09:10:00Z',
        updatedBy: 'sema.ozturk'
      },
      {
        moduleKey: 'AUDIT_TRAIL',
        moduleLabel: 'Audit Kayıtları',
        level: 'VIEW',
        lastUpdatedAt: '2025-09-21T12:40:00Z',
        updatedBy: 'selim.tas'
      }
    ]
  },
  {
    id: 'role-analytics',
    name: 'Raporlama Analisti',
    description: 'Rapor ve içgörü üretimi için erişimler.',
    memberCount: 6,
    lastModifiedAt: '2025-10-01T11:37:00Z',
    lastModifiedBy: 'eda.aksoy',
    permissions: ['MANAGE_REPORTS', 'VIEW_AUDIT'],
    policies: [
      {
        moduleKey: 'REPORTING',
        moduleLabel: 'Raporlama',
        level: 'MANAGE',
        lastUpdatedAt: '2025-10-01T11:37:00Z',
        updatedBy: 'eda.aksoy'
      },
      {
        moduleKey: 'AUDIT_TRAIL',
        moduleLabel: 'Audit Kayıtları',
        level: 'VIEW',
        lastUpdatedAt: '2025-09-15T09:35:00Z',
        updatedBy: 'eda.aksoy'
      }
    ]
  }
];
