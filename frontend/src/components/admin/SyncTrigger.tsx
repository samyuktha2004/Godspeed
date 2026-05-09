import { useState } from 'react'
import { apiFetch, ApiError } from '@/lib/http'
import { useUIStore } from '@/stores/uiStore'
import { cn } from '@/lib/utils'

interface Props {
  source:    'jira' | 'confluence'
  /** project key for Jira, space key for Confluence */
  sourceKey: string
  label:     string
  lastSynced?: string
}

export function SyncTrigger({ source, sourceKey, label, lastSynced }: Props) {
  const [taskId, setTaskId]   = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const addToast              = useUIStore((s) => s.addToast)

  const trigger = async () => {
    setLoading(true)
    try {
      const path = source === 'jira'
        ? `/jira/sync/${sourceKey}`
        : `/confluence/sync/${sourceKey}`
      const res  = await apiFetch(path, { method: 'POST' })
      const data = await res.json() as { task_id: string }
      setTaskId(data.task_id)
      addToast({ type: 'success', message: `${label} sync queued` })
    } catch (err) {
      if (!(err instanceof ApiError)) {
        addToast({ type: 'error', message: `Failed to trigger ${label} sync` })
      }
      // ApiError toasts are handled in apiFetch
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex items-center justify-between rounded-lg border border-surface-subtle p-4">
      <div>
        <p className="text-sm font-medium">{label}</p>
        {lastSynced && (
          <p className="text-xs text-stone-500">Last synced {lastSynced}</p>
        )}
        {taskId && (
          <p className="mt-0.5 font-mono text-xs text-stone-400">Task {taskId.slice(0, 8)}…</p>
        )}
      </div>
      <button
        onClick={trigger}
        disabled={loading}
        className={cn(
          'rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
          loading
            ? 'cursor-not-allowed bg-stone-100 text-stone-400 dark:bg-stone-800'
            : 'bg-brand text-white hover:bg-brand-dark',
        )}
      >
        {loading ? 'Queuing…' : 'Sync now'}
      </button>
    </div>
  )
}
