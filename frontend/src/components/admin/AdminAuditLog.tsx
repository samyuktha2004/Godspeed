import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/lib/http'
import { AuditLogEntry } from '@/types/settings'
import { LoadingSkeleton } from '../common/LoadingSkeleton'

const ACTION_ICONS: Record<string, string> = {
  grant_channel: '✅',
  revoke_channel: '❌',
  change_role: '👤',
  invite_user: '📨',
  deactivate_user: '🚫',
  query_executed: '🔍',
  document_accessed: '📄',
  bulk_user_import: '📥',
}

const ACTION_COLORS: Record<string, string> = {
  grant_channel: 'text-green-600 dark:text-green-400',
  revoke_channel: 'text-red-600 dark:text-red-400',
  change_role: 'text-blue-600 dark:text-blue-400',
  invite_user: 'text-purple-600 dark:text-purple-400',
  deactivate_user: 'text-red-600 dark:text-red-400',
  query_executed: 'text-stone-600 dark:text-stone-400',
  document_accessed: 'text-stone-600 dark:text-stone-400',
  bulk_user_import: 'text-green-600 dark:text-green-400',
}

export function AdminAuditLog() {
  const [filterAction, setFilterAction] = useState<string>('all')
  const [filterType, setFilterType] = useState<string>('all')

  // Fetch audit log
  const { data: auditEntries, isLoading, refetch } = useQuery({
    queryKey: ['audit-log', filterAction, filterType],
    queryFn: async () => {
      // TODO: GET /api/audit-log?action=X&target_type=Y
      return [] as AuditLogEntry[]
    },
  })

  const allActions = [
    'grant_channel',
    'revoke_channel',
    'change_role',
    'invite_user',
    'deactivate_user',
    'query_executed',
    'document_accessed',
    'bulk_user_import',
  ]

  const allTargetTypes = ['user', 'channel', 'team', 'query', 'document']

  const handleExportCSV = () => {
    // TODO: GET /api/audit-log/export?format=csv
    console.log('Export audit log as CSV')
  }

  return (
    <div className="space-y-6 p-6">
      {/* Filters & Export */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="flex gap-2">
          <div>
            <label className="block text-xs font-medium text-stone-700 dark:text-stone-300">
              Filter by Action
            </label>
            <select
              value={filterAction}
              onChange={(e) => setFilterAction(e.target.value)}
              className="mt-1 rounded border border-stone-300 bg-white px-2 py-1 text-xs text-stone-900 focus:border-brand focus:outline-none dark:border-stone-600 dark:bg-stone-800 dark:text-white"
            >
              <option value="all">All Actions</option>
              {allActions.map((action) => (
                <option key={action} value={action}>
                  {action.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium text-stone-700 dark:text-stone-300">
              Filter by Target
            </label>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="mt-1 rounded border border-stone-300 bg-white px-2 py-1 text-xs text-stone-900 focus:border-brand focus:outline-none dark:border-stone-600 dark:bg-stone-800 dark:text-white"
            >
              <option value="all">All Types</option>
              {allTargetTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>
        </div>

        <button
          onClick={handleExportCSV}
          className="rounded border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 hover:bg-stone-50 dark:border-stone-600 dark:text-stone-300 dark:hover:bg-stone-800"
        >
          📊 Export as CSV
        </button>
      </div>

      {/* Audit Log Entries */}
      <div>
        <h3 className="mb-3 text-sm font-semibold">Recent Activity</h3>
        {isLoading ? (
          <LoadingSkeleton count={5} height="h-12" />
        ) : auditEntries && auditEntries.length > 0 ? (
          <div className="space-y-2 rounded-lg border border-stone-200 dark:border-stone-700">
            {auditEntries.map((entry) => (
              <div
                key={entry.id}
                className="flex items-start gap-3 border-b border-stone-200 p-3 last:border-b-0 dark:border-stone-700"
              >
                <span className={`text-lg ${ACTION_COLORS[entry.action] || 'text-stone-500'}`}>
                  {ACTION_ICONS[entry.action] || '•'}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="text-sm font-medium text-stone-900 dark:text-white">
                        {entry.action.replace(/_/g, ' ')}
                      </p>
                      <p className="text-xs text-stone-600 dark:text-stone-400">
                        {entry.actor_name && `by ${entry.actor_name}`}
                        {entry.actor_name && entry.target_name && ' • '}
                        {entry.target_name && `on ${entry.target_name}`}
                      </p>
                    </div>
                    <span className="text-xs text-stone-500 dark:text-stone-500 whitespace-nowrap">
                      {new Date(entry.created_at).toLocaleDateString()} {new Date(entry.created_at).toLocaleTimeString()}
                    </span>
                  </div>

                  {/* Metadata if available */}
                  {Object.keys(entry.metadata).length > 0 && (
                    <details className="mt-2">
                      <summary className="cursor-pointer text-xs font-medium text-stone-500 hover:text-stone-700 dark:hover:text-stone-300">
                        Details
                      </summary>
                      <pre className="mt-1 overflow-x-auto rounded bg-stone-100 p-2 text-xs text-stone-700 dark:bg-stone-800 dark:text-stone-300">
                        {JSON.stringify(entry.metadata, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border-2 border-dashed border-stone-300 p-8 text-center dark:border-stone-600">
            <p className="text-sm text-stone-500">No audit log entries yet</p>
            <p className="mt-1 text-xs text-stone-400">
              Actions will appear here as users and admins interact with the system
            </p>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="rounded-lg border border-stone-200 bg-stone-50 p-4 dark:border-stone-700 dark:bg-stone-900">
        <h4 className="text-xs font-semibold text-stone-900 dark:text-white">What's tracked?</h4>
        <ul className="mt-2 space-y-1 text-xs text-stone-600 dark:text-stone-400">
          <li>• <strong>User actions:</strong> invite, deactivate, role changes</li>
          <li>• <strong>Channel access:</strong> grants and revokes</li>
          <li>• <strong>Bulk operations:</strong> CSV imports, bulk role updates</li>
          <li>• <strong>Query activity:</strong> who searched what, when</li>
          <li>• <strong>Document access:</strong> restricted document views (compliance)</li>
        </ul>
      </div>
    </div>
  )
}
