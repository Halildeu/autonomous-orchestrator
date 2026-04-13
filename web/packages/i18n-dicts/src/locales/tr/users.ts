const users = {
  'users.layout.title': 'Kullanıcı Yönetimi',
  'users.layout.description':
    'Kullanıcıların rol ve modül yetkilerini yönetin, hesap güvenliği ile ilgili işlemleri tanımlayın.',
  'admin.users.title': 'Kullanıcı Yönetimi',
  'admin.users.description':
    'Kullanıcıların rol ve modül yetkilerini yönetin, hesap güvenliği ile ilgili işlemleri tanımlayın.',
  'users.breadcrumb.management': 'Yönetim',
  'users.breadcrumb.users': 'Kullanıcı Yönetimi',

  'users.actions.refresh': 'Kullanıcıları Yenile',

  // Grid toolbar
  'users.grid.themeLabel': 'Tema',
  'users.grid.quickFilterLabel': 'Filtre',
  'users.grid.variantLabel': 'Varyant',
  'users.grid.quickFilterPlaceholder': 'Tüm sütunlarda ara...',
  'users.grid.fullscreenTooltip': 'Yeni sekmede tam ekran aç',

  'users.grid.mode.label': 'Veri modu:',
  'users.grid.mode.server': 'Sunucu',
  'users.grid.mode.client': 'İstemci',

  // Filter panel
  'users.filters.search.label': 'Arama',
  'users.filters.search.placeholder': 'Ad, e-posta veya ID',
  'users.filters.search.button': 'Ara',

  'users.filters.status.label': 'Durum',
  'users.filters.status.all': 'Tümü',
  'users.filters.status.active': 'Aktif',
  'users.filters.status.inactive': 'Pasif',
  'users.filters.status.invited': 'Davet edildi',
  'users.filters.status.suspended': 'Askıya alındı',

  'users.filters.role.label': 'Rol',
  'users.filters.role.all': 'Tümü',
  'users.filters.role.user': 'Standart Kullanıcı',
  'users.filters.role.admin': 'Admin',

  'users.filters.moduleKey.label': 'Modül Anahtarı',
  'users.filters.moduleKey.placeholder': 'finance.users',

  'users.filters.moduleLevel.label': 'Modül Seviyesi',
  'users.filters.moduleLevel.all': 'Tümü',
  'users.filters.moduleLevel.none': 'Yetki yok',
  'users.filters.moduleLevel.view': 'Görüntüleyici',
  'users.filters.moduleLevel.edit': 'Düzenleyici',
  'users.filters.moduleLevel.manage': 'Sahip',

  'users.filters.apply': 'Filtrele',
  'users.filters.reset': 'Sıfırla',

  // Grid columns
  'users.grid.columns.fullName': 'Ad Soyad',
  'users.grid.columns.email': 'E-posta',
  'users.grid.columns.role': 'Rol',
  'users.grid.columns.status': 'Durum',
  'users.grid.columns.sessionTimeoutMinutes': 'Oturum Süresi (dk)',
  'users.grid.columns.modulePermissions': 'Modül Yetkileri',
  'users.grid.columns.lastLoginAt': 'Son Giriş',
  'users.grid.columns.actions': 'İşlemler',

  // Toolbar actions (export/reset)
  'users.grid.toolbar.resetFilters': 'Filtreleri Sıfırla',
  'users.grid.toolbar.excelVisible': 'Excel (Görünür)',
  'users.grid.toolbar.excelAll': 'Excel (Tümü)',
  'users.grid.toolbar.csvVisible': 'CSV (Görünür)',
  'users.grid.toolbar.csvAll': 'CSV (Tümü)',

  // AG Grid side panel / advanced filter
  'users.grid.locale.groupPanel': 'Gruplamak için sütunları buraya sürükleyin',
  'users.grid.locale.valuePanel': 'Değerler için sütunları buraya sürükleyin',
  'users.grid.locale.filters': 'Filtreler',
  'users.grid.locale.columns': 'Sütunlar',
  'users.grid.locale.advancedFilter': 'Gelişmiş filtre',
  'users.grid.locale.advancedFilterBuilder': 'Gelişmiş filtre',
  'users.grid.locale.advancedFilterButtonTooltip': 'Gelişmiş filtreyi aç',
  'users.grid.locale.advancedFilterBuilderAdd': 'Koşul ekle',
  'users.grid.locale.advancedFilterBuilderRemove': 'Kaldır',
  'users.grid.locale.advancedFilterJoinOperator': 'Bağlaç',
  'users.grid.locale.advancedFilterAnd': 'VE',
  'users.grid.locale.advancedFilterOr': 'VEYA',
  'users.grid.locale.advancedFilterValidationMissingColumn': 'Sütun seçin',
  'users.grid.locale.advancedFilterValidationMissingOption': 'Operatör seçin',
  'users.grid.locale.advancedFilterValidationMissingValue': 'Değer girin',
  'users.grid.locale.advancedFilterApply': 'Uygula',

  // Actions menu (grid row)
  'users.actions.menuLabel': 'İşlemler ▾',
  'users.actions.view': 'Detayı Görüntüle',
  'users.actions.editRole': 'Rol / Yetki Düzenle',
  'users.actions.resetPassword': 'Parolayı Sıfırla',
  'users.actions.toggleStatus.disable': 'Pasifleştir',
  'users.actions.toggleStatus.enable': 'Aktifleştir',
  'users.actions.resetPassword.success': 'Parola sıfırlama bağlantısı gönderildi.',
  'users.actions.status.success': 'Kullanıcı durumu güncellendi.',
  'users.notifications.activation.description': 'Audit ID: {auditId}',

  // Detay çekmecesi – başlıklar & bölümler
  'users.detail.title': 'Kullanıcı Detayı',
  'users.detail.section.profile': 'Profil Bilgileri',
  'users.detail.section.permissions': 'Modül Yetkileri',
  'users.detail.section.quickActions': 'Hızlı İşlemler',

  // Detay çekmecesi – oturum süresi
  'users.detail.sessionTimeout.unit': 'dakika',
  'users.detail.sessionTimeout.saving': 'Kaydediliyor...',
  'users.detail.sessionTimeout.save': 'Kaydet',
  'users.detail.sessionTimeout.minWarning': 'Oturum süresi en az 1 dakika olmalıdır.',
  'users.detail.sessionTimeout.noChange': 'Oturum süresi zaten bu değerde.',
  'users.detail.sessionTimeout.updated': 'Oturum süresi güncellendi.',
  'users.detail.sessionTimeout.updateFailed': 'Oturum süresi güncellenemedi.',

  // Detay çekmecesi – rol & durum
  'users.detail.roleUpdated': 'Kullanıcı rolü güncellendi.',

  // Detay çekmecesi – modül yetkileri
  'users.detail.noModulePermissions': 'Tanımlı modül yetkisi bulunmuyor.',
  'users.detail.noPermissionDetails': 'Yetki detayı bulunmuyor',
  'users.detail.scopeMissingHint': 'Şirket/dönem seçimi olmadığı için yetki düzenlenemez.',
  'users.detail.noAccessWarning':
    'Bu modül için yetki bulunmuyor; kullanıcı ilgili raporlara erişemez.',
  'users.detail.userManagementScopeHint':
    'Kullanıcı Yönetimi yetkileri şirket/dönem seçimi ile verilmelidir.',
  'users.detail.modulePermission.noActive': 'Bu modül için aktif yetki bulunmuyor.',
  'users.detail.modulePermission.removed': '{module} yetkisi kaldırıldı.',
  'users.detail.modulePermission.updated': '{module} yetkisi güncellendi.',
  'users.detail.modulePermission.updating': 'Yetki güncelleniyor...',

  // Detay çekmecesi – modül seviye açıklamaları
  'users.detail.moduleLevelDescription.none': 'Bu modüle erişimi yok',
  'users.detail.moduleLevelDescription.view': 'Yalnızca görüntüleme yetkisi',
  'users.detail.moduleLevelDescription.edit': 'Düzenleme yetkisi',
  'users.detail.moduleLevelDescription.manage': 'Tam yönetim yetkisi',

  // Detay çekmecesi – hızlı işlemler
  'users.detail.quickActions.noteSoon': 'Not Ekle (yakında)',

  // Faz 2: Multi-role + tabbed scope
  'users.detail.section.roles': 'Roller',
  'users.detail.section.roles.description': 'Kullanıcıya birden fazla rol atayabilirsiniz. İzinler rollerin birleşimidir.',
  'users.detail.section.scopes': 'Veri Erişimi',
  'users.detail.section.scopes.description': 'Scope atanmadan kullanıcı hiçbir veri göremez.',
  'users.detail.scopes.companies': 'Şirketler',
  'users.detail.scopes.projects': 'Projeler',
  'users.detail.scopes.warehouses': 'Depolar',
  'users.detail.scopes.branches': 'Şubeler',
  'users.detail.scopes.selectAll': 'Tümünü Seç',
  'users.detail.save': 'Kaydet',
  'users.detail.saving': 'Kaydediliyor...',
  'users.detail.cancel': 'Vazgeç',
  'users.detail.noRolesDefined': 'Henüz rol tanımlanmamış.',
  'users.detail.noRolesWarning': 'En az bir rol seçilmelidir.',
  'users.detail.loadingRoles': 'Yükleniyor...',
  'users.detail.assignmentSaved': 'Rol ve erişim atamaları kaydedildi.',
  'users.grid.columns.roles': 'Roller',
};

export default users;
