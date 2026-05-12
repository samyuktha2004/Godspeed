import { useState } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { AdminUserManagement } from './AdminUserManagement'
import { AdminChannelManagement } from './AdminChannelManagement'
import { AdminAuditLog } from './AdminAuditLog'
import { AdminWorkspaceSettings } from './AdminWorkspaceSettings'

type AdminTab = 'users' | 'channels' | 'audit' | 'workspace'

const TABS: { id: AdminTab; label: string }[] = [
  { id: 'users', label: 'Users' },
  { id: 'channels', label: 'Channels' },
  { id: 'audit', label: 'Audit Log' },
  { id: 'workspace', label: 'Workspace' },
]

export function AdminWorkspace() {
  const { user } = useAuth()
  const [tab, setTab] = useState<AdminTab>('users')

  // Only admins and org_admins can access this
  if (!user || (user.role !== 'admin' && user.role !== 'manager')) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center dark:border-red-900 dark:bg-red-950">
        <p className="text-sm font-semibold text-red-900 dark:text-red-200">
          You don't have permission to access the admin panel
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Admin Workspace</h2>
          <p className="text-xs text-stone-500">Manage users, channels, and audit logs</p>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 overflow-x-auto border-b border-stone-200 dark:border-stone-700">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`whitespace-nowrap px-3 py-2 text-sm font-medium transition-colors ${
              tab === t.id
                ? 'border-b-2 border-brand text-brand'
                : 'text-stone-500 hover:text-stone-700 dark:hover:text-stone-300'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="rounded-lg border border-stone-200 bg-white dark:border-stone-700 dark:bg-stone-900">
        {tab === 'users' && <AdminUserManagement />}
        {tab === 'channels' && <AdminChannelManagement />}
        {tab === 'audit' && <AdminAuditLog />}
        {tab === 'workspace' && <AdminWorkspaceSettings />}
      </div>
    </div>
  )
}
