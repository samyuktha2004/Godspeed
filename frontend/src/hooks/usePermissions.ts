import { useAuth } from '@/hooks/useAuth'
import type { PermissionKey } from '@/lib/permissions'
import { ROLE_PERMISSIONS } from '@/lib/permissions'

export function usePermissions() {
  const { user } = useAuth()

  const permissions: PermissionKey[] = user
    ? (user as { permissions?: PermissionKey[] }).permissions ??
      ROLE_PERMISSIONS[user.role] ??
      []
    : []

  function can(perm: PermissionKey): boolean {
    return permissions.includes(perm)
  }

  function canAny(...perms: PermissionKey[]): boolean {
    return perms.some((p) => permissions.includes(p))
  }

  function canAll(...perms: PermissionKey[]): boolean {
    return perms.every((p) => permissions.includes(p))
  }

  return { can, canAny, canAll, permissions }
}
