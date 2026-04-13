const users = {
  'users.layout.title': 'User Management',
  'users.layout.description':
    'Manage user roles, permissions and module access; define account security-related operations.',
  'admin.users.title': 'User Management',
  'admin.users.description':
    'Manage user roles, permissions and module access; define account security-related operations.',
  'users.breadcrumb.management': 'Administration',
  'users.breadcrumb.users': 'User Management',

  'users.actions.refresh': 'Refresh users',

  // Grid toolbar
  'users.grid.themeLabel': 'Theme',
  'users.grid.quickFilterLabel': 'Filter',
  'users.grid.variantLabel': 'Variant',
  'users.grid.quickFilterPlaceholder': 'Search all columns...',
  'users.grid.fullscreenTooltip': 'Open fullscreen in a new tab',

  'users.grid.mode.label': 'Data mode:',
  'users.grid.mode.server': 'Server',
  'users.grid.mode.client': 'Client',

  // Filter panel
  'users.filters.search.label': 'Search',
  'users.filters.search.placeholder': 'Name, email or ID',
  'users.filters.search.button': 'Search',

  'users.filters.status.label': 'Status',
  'users.filters.status.all': 'All',
  'users.filters.status.active': 'Active',
  'users.filters.status.inactive': 'Inactive',
  'users.filters.status.invited': 'Invited',
  'users.filters.status.suspended': 'Suspended',

  'users.filters.role.label': 'Role',
  'users.filters.role.all': 'All',
  'users.filters.role.user': 'Standard User',
  'users.filters.role.admin': 'Admin',

  'users.filters.moduleKey.label': 'Module key',
  'users.filters.moduleKey.placeholder': 'finance.users',

  'users.filters.moduleLevel.label': 'Module level',
  'users.filters.moduleLevel.all': 'All',
  'users.filters.moduleLevel.none': 'No access',
  'users.filters.moduleLevel.view': 'Viewer',
  'users.filters.moduleLevel.edit': 'Editor',
  'users.filters.moduleLevel.manage': 'Owner',

  'users.filters.apply': 'Apply',
  'users.filters.reset': 'Reset',

  // Grid columns
  'users.grid.columns.fullName': 'Full name',
  'users.grid.columns.email': 'Email',
  'users.grid.columns.role': 'Role',
  'users.grid.columns.status': 'Status',
  'users.grid.columns.sessionTimeoutMinutes': 'Session duration (min)',
  'users.grid.columns.modulePermissions': 'Module permissions',
  'users.grid.columns.lastLoginAt': 'Last login',
  'users.grid.columns.actions': 'Actions',

  // Toolbar actions (export/reset)
  'users.grid.toolbar.resetFilters': 'Reset filters',
  'users.grid.toolbar.excelVisible': 'Excel (Visible)',
  'users.grid.toolbar.excelAll': 'Excel (All)',
  'users.grid.toolbar.csvVisible': 'CSV (Visible)',
  'users.grid.toolbar.csvAll': 'CSV (All)',

  // AG Grid side panel / advanced filter
  'users.grid.locale.groupPanel': 'Drag columns here to group',
  'users.grid.locale.valuePanel': 'Drag columns here to aggregate values',
  'users.grid.locale.filters': 'Filters',
  'users.grid.locale.columns': 'Columns',
  'users.grid.locale.advancedFilter': 'Advanced filter',
  'users.grid.locale.advancedFilterBuilder': 'Advanced filter',
  'users.grid.locale.advancedFilterButtonTooltip': 'Open advanced filter',
  'users.grid.locale.advancedFilterBuilderAdd': 'Add condition',
  'users.grid.locale.advancedFilterBuilderRemove': 'Remove',
  'users.grid.locale.advancedFilterJoinOperator': 'Join operator',
  'users.grid.locale.advancedFilterAnd': 'AND',
  'users.grid.locale.advancedFilterOr': 'OR',
  'users.grid.locale.advancedFilterValidationMissingColumn': 'Select column',
  'users.grid.locale.advancedFilterValidationMissingOption': 'Select operator',
  'users.grid.locale.advancedFilterValidationMissingValue': 'Enter value',
  'users.grid.locale.advancedFilterApply': 'Apply',

  // Actions menu (grid row)
  'users.actions.menuLabel': 'Actions ▾',
  'users.actions.view': 'View details',
  'users.actions.editRole': 'Edit role / permissions',
  'users.actions.resetPassword': 'Reset password',
  'users.actions.toggleStatus.disable': 'Deactivate',
  'users.actions.toggleStatus.enable': 'Activate',
  'users.actions.resetPassword.success': 'Password reset link has been sent.',
  'users.actions.status.success': 'User status has been updated.',
  'users.notifications.activation.description': 'Audit ID: {auditId}',

  // Detail drawer – titles & sections
  'users.detail.title': 'User Details',
  'users.detail.section.profile': 'Profile information',
  'users.detail.section.permissions': 'Module permissions',
  'users.detail.section.quickActions': 'Quick actions',

  // Detail drawer – session timeout
  'users.detail.sessionTimeout.unit': 'minutes',
  'users.detail.sessionTimeout.saving': 'Saving...',
  'users.detail.sessionTimeout.save': 'Save',
  'users.detail.sessionTimeout.minWarning': 'Session duration must be at least 1 minute.',
  'users.detail.sessionTimeout.noChange': 'Session duration is already set to this value.',
  'users.detail.sessionTimeout.updated': 'Session duration has been updated.',
  'users.detail.sessionTimeout.updateFailed': 'Failed to update session duration.',

  // Detail drawer – role & status
  'users.detail.roleUpdated': 'User role has been updated.',

  // Detail drawer – module permissions
  'users.detail.noModulePermissions': 'No module permissions are defined.',
  'users.detail.noPermissionDetails': 'No permission details available',
  'users.detail.scopeMissingHint':
    'Permissions cannot be edited because no company/period scope is selected.',
  'users.detail.noAccessWarning':
    'The user has no access to this module and cannot see related reports.',
  'users.detail.userManagementScopeHint':
    'User Management permissions must be granted with a selected company/period.',
  'users.detail.modulePermission.noActive': 'There is no active permission for this module.',
  'users.detail.modulePermission.removed': 'Permission for {module} has been removed.',
  'users.detail.modulePermission.updated': 'Permission for {module} has been updated.',
  'users.detail.modulePermission.updating': 'Updating permission...',

  // Detail drawer – module level descriptions
  'users.detail.moduleLevelDescription.none': 'No access to this module',
  'users.detail.moduleLevelDescription.view': 'View-only access',
  'users.detail.moduleLevelDescription.edit': 'Edit access',
  'users.detail.moduleLevelDescription.manage': 'Full administrative access',

  // Detail drawer – quick actions
  'users.detail.quickActions.noteSoon': 'Add note (coming soon)',

  // Phase 2: Multi-role + tabbed scope
  'users.detail.section.roles': 'Roles',
  'users.detail.section.roles.description': 'Assign multiple roles to the user. Permissions are the union of all assigned roles.',
  'users.detail.section.scopes': 'Data Access',
  'users.detail.section.scopes.description': 'Without scope assignment, the user cannot see any data.',
  'users.detail.scopes.companies': 'Companies',
  'users.detail.scopes.projects': 'Projects',
  'users.detail.scopes.warehouses': 'Warehouses',
  'users.detail.scopes.branches': 'Branches',
  'users.detail.scopes.selectAll': 'Select All',
  'users.detail.save': 'Save',
  'users.detail.saving': 'Saving...',
  'users.detail.cancel': 'Cancel',
  'users.detail.noRolesDefined': 'No roles defined yet.',
  'users.detail.noRolesWarning': 'At least one role must be selected.',
  'users.detail.loadingRoles': 'Loading...',
  'users.detail.assignmentSaved': 'Role and access assignments saved.',
  'users.grid.columns.roles': 'Roles',
};

export default users;
