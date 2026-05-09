import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '@/lib/http'
import { useUIStore } from '@/stores/uiStore'
import { cn } from '@/lib/utils'
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton'

interface DataSource {
  id:           string
  type:         'jira' | 'confluence' | 'github' | 'slack'
  name:         string
  url:          string
  enabled:      boolean
  last_sync:    string | null
  sync_status:  'idle' | 'syncing' | 'error'
  error_msg:    string | null
}

async function fetchSources(): Promise<{ sources: DataSource[] }> {
  const res = await apiFetch('/api/admin/data-sources')
  return res.json()
}

async function toggleSource(id: string, enabled: boolean): Promise<void> {
  await apiFetch(`/api/admin/data-sources/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body:   JSON.stringify({ enabled }),
  })
}

const TYPE_ICONS: Record<DataSource['type'], string> = {
  jira:       '🔷',
  confluence: '📘',
  github:     '🐙',
  slack:      '💬',
}

const SYNC_STATUS_STYLES: Record<DataSource['sync_status'], string> = {
  idle:    'text-stone-400',
  syncing: 'text-blue-500',
  error:   'text-red-500',
}

export function DataSourceManager() {
  const qc       = useQueryClient()
  const addToast = useUIStore((s) => s.addToast)
  const [adding, setAdding] = useState(false)

  const { data, isLoading } = useQuery({
    queryKey:  ['admin-data-sources'],
    queryFn:   fetchSources,
    staleTime: 60_000,
  })

  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => toggleSource(id, enabled),
    onSuccess:  () => qc.invalidateQueries({ queryKey: ['admin-data-sources'] }),
    onError:    () => addToast({ type: 'error', message: 'Failed to update data source' }),
  })

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-stone-500">Connected Data Sources</p>
        <button
          onClick={() => setAdding(true)}
          className="rounded-lg bg-brand px-3 py-1.5 text-xs font-medium text-white hover:bg-brand/90"
        >
          + Add source
        </button>
      </div>

      {isLoading ? (
        <div className="rounded-xl border border-surface-subtle p-5">
          <LoadingSkeleton rows={4} />
        </div>
      ) : (data?.sources ?? []).length === 0 ? (
        <div className="rounded-xl border border-dashed border-surface-subtle py-16 text-center">
          <p className="text-sm text-stone-400">No data sources configured.</p>
          <button
            onClick={() => setAdding(true)}
            className="mt-3 text-sm font-medium text-brand hover:underline"
          >
            Add your first source →
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {(data?.sources ?? []).map((src) => (
            <div
              key={src.id}
              className={cn(
                'rounded-xl border p-4 transition-colors',
                src.enabled
                  ? 'border-surface-subtle'
                  : 'border-dashed border-stone-200 opacity-60 dark:border-stone-700',
              )}
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 text-xl" aria-hidden>{TYPE_ICONS[src.type]}</span>
                  <div>
                    <p className="font-medium">{src.name}</p>
                    <p className="text-xs text-stone-400">{src.url}</p>
                    {src.sync_status === 'error' && src.error_msg && (
                      <p className="mt-1 text-xs text-red-500">{src.error_msg}</p>
                    )}
                    <p className={cn('mt-1 text-xs capitalize', SYNC_STATUS_STYLES[src.sync_status])}>
                      {src.sync_status === 'syncing'
                        ? 'Syncing…'
                        : src.last_sync
                          ? `Last sync: ${new Date(src.last_sync).toLocaleDateString()}`
                          : 'Never synced'}
                    </p>
                  </div>
                </div>

                {/* Toggle */}
                <button
                  role="switch"
                  aria-checked={src.enabled}
                  onClick={() => toggle.mutate({ id: src.id, enabled: !src.enabled })}
                  className={cn(
                    'relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors',
                    src.enabled ? 'bg-brand' : 'bg-stone-200 dark:bg-stone-700',
                  )}
                >
                  <span
                    className={cn(
                      'pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-sm transition-transform',
                      src.enabled ? 'translate-x-5' : 'translate-x-0',
                    )}
                  />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add source placeholder modal hint */}
      {adding && (
        <div className="rounded-xl border border-brand/30 bg-amber-50 p-5 dark:bg-amber-950/20">
          <p className="text-sm font-medium text-stone-700 dark:text-stone-300">
            Data source wizard — configure integration credentials in <code className="rounded bg-stone-100 px-1 py-0.5 text-xs dark:bg-stone-800">.env</code> and register via the API.
          </p>
          <p className="mt-1 text-xs text-stone-500">
            See <code className="rounded bg-stone-100 px-1 py-0.5 dark:bg-stone-800">POST /api/admin/data-sources</code> in the API docs.
          </p>
          <button
            onClick={() => setAdding(false)}
            className="mt-3 text-xs font-medium text-stone-500 hover:text-stone-700"
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  )
}
