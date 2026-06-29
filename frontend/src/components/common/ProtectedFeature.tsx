import type { ReactNode } from 'react'
import { usePermissions } from '@/hooks/usePermissions'
import type { PermissionKey } from '@/lib/permissions'

interface Props {
  perm: PermissionKey
  fallback?: ReactNode
  children: ReactNode
}

export function ProtectedFeature({ perm, fallback = null, children }: Props) {
  const { can } = usePermissions()
  return can(perm) ? <>{children}</> : <>{fallback}</>
}
