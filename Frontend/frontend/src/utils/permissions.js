export const ROLES = {
  ADMIN: 'admin',
  CUSTOMER_SERVICE: 'customer_service',
  OPERATIONAL: 'operational',
  MANAGER: 'manager',
  OPERATOR: 'operator',
}

export function hasRole(user, role) {
  return String(user?.role ?? '').toLowerCase().trim() === String(role).toLowerCase().trim()
}

export function hasAnyRole(user, roles = []) {
  const userRole = String(user?.role ?? '').toLowerCase().trim()
  return roles.map((r) => String(r).toLowerCase().trim()).includes(userRole)
}

export const isAdmin = (user) => hasRole(user, ROLES.ADMIN)
export const isCustomerService = (user) => hasRole(user, ROLES.CUSTOMER_SERVICE)
export const isOperational = (user) => hasRole(user, ROLES.OPERATIONAL) || hasRole(user, ROLES.OPERATOR)

export const canManageApprovals = (user) => {
  if (!user) return false
  if (user.can_approve_commitments === true) return true
  if (isAdmin(user) || hasRole(user, ROLES.MANAGER)) return true
  return false
}

export const canManageUsers = (user) => isAdmin(user)
export const canConfigureSettings = (user) => isAdmin(user)

export const canAcknowledgeAlert = (user, alertDepartment) => {
  if (!user) return false
  if (isAdmin(user) || hasRole(user, ROLES.MANAGER)) return true
  if (isCustomerService(user)) return false // CS cannot modify operational department findings
  if (isOperational(user)) {
    if (!user.department) return true
    return user.department.toUpperCase().trim() === String(alertDepartment || '').toUpperCase().trim()
  }
  return false
}

export const canResolveAlert = (user, alertDepartment) => {
  if (!user) return false
  if (isAdmin(user) || hasRole(user, ROLES.MANAGER)) return true
  if (isCustomerService(user)) return false // CS cannot resolve operational findings
  if (isOperational(user)) {
    if (!user.department) return true
    return user.department.toUpperCase().trim() === String(alertDepartment || '').toUpperCase().trim()
  }
  return false
}

export const canRecordCustomerCommunication = (user) => {
  if (!user) return false
  return isCustomerService(user) || isAdmin(user) || hasRole(user, ROLES.MANAGER)
}

export function hasPermission(user, permission) {
  if (!user) return false
  if (isAdmin(user)) return true
  if (Array.isArray(user.permissions)) {
    return user.permissions.includes(permission)
  }
  return false
}

export const canUseOperationalFeatures = (user) => Boolean(user)
