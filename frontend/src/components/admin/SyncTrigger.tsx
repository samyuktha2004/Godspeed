import { useState, useEffect, useRef } from 'react'
import { apiFetch, ApiError } from '@/lib/http'
import { useUIStore } from '@/stores/uiStore'
import { cn } from '@/lib/utils'

type JobStatus = 'pending' | 'running' | 'completed' | 'failed'

interface Props {
  source:    'jira' | 'confluence'
  sourceKey: string
  label:     string
  lastSynced?: string
}

const STATUS_LABEL: Record<JobStatus, string> = {
  pending:   'Queued…',
  running:   'Syncing…',
  completed: 'Sync complete',
  failed:    'Sync failed',
}

const STATUS_COLOR: Record<JobStatus, string> = {
  pending:   'text-stone-400',
  running:   'text-blue-500',
  completed: 'text-green-600',
  failed:    'text-red-500',
}

export function SyncTrigger({ source, sourceKey, label, lastSynced }: Props) {
  const [taskId,    setTaskId]    = useState<string | null>(null)
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null)
  const [loading,   setLoading]   = useState(false)
  const addToast = useUIStore((s) => s.addToast)
  const pollRef  = useRef<ReturnType<typeof setInterval> | null>(null)

  // Poll job status until terminal state
  useEffect(() => {
    if (!taskId) return
    if (pollRef.current) clearInterval(pollRef.current)

    const poll = async () => {
      try {
        const res  = await apiFetch(`/ingest/jobs/${taskId}`)
        const data = await res.json() as { status: JobStatus }
        setJobStatus(data.status)
        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(pollRef.current!)
          pollRef.current = null
          addToast({
            type:    data.status === 'completed' ? 'success' : 'error',
            message: data.status === 'completed'
              ? `${label} sync finished`
              : `${label} sync failed`,
          })
        }
      } catch { /* ignore poll errors */ }
    }

    poll() // immediate first check
    pollRef.current = setInterval(poll, 4000)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [taskId]) // eslint-disable-line react-hooks/exhaustive-deps

  const trigger = async () => {
    setLoading(true)
    setTaskId(null)
    setJobStatus(null)
    try {
      const path = source === 'jira'
        ? `/jira/sync/${sourceKey}`
        : `/confluence/sync/${sourceKey}`
      const res  = await apiFetch(path, { method: 'POST' })
      const data = await res.json() as { task_id: string }
      setTaskId(data.task_id)
      setJobStatus('pending')
      addToast({ type: 'success', message: `${label} sync queued` })
    } catch (err) {
      if (!(err instanceof ApiError)) {
        addToast({ type: 'error', message: `Failed to trigger ${label} sync` })
      }
    } finally {
      setLoading(false)
    }
  }

  const isBusy = loading || jobStatus === 'pending' || jobStatus === 'running'

  return (
    <div className="flex items-center justify-between rounded-lg border border-surface-subtle p-4">
      <div>
        <p className="text-sm font-medium">{label}</p>
        {lastSynced && !jobStatus && (
          <p className="text-xs text-stone-500">Last synced {lastSynced}</p>
        )}
        {jobStatus && (
          <div className="mt-1 flex items-center gap-1.5">
            {(jobStatus === 'pending' || jobStatus === 'running') && (
              <span className="inline-block h-2.5 w-2.5 animate-spin rounded-full border-2 border-blue-300 border-t-blue-600" />
            )}
            <p className={cn('text-xs font-medium', STATUS_COLOR[jobStatus])}>
              {STATUS_LABEL[jobStatus]}
            </p>
          </div>
        )}
        {taskId && (
          <p className="mt-0.5 font-mono text-[10px] text-stone-400">
            Task {taskId.slice(0, 8)}…
          </p>
        )}
      </div>
      <button
        onClick={trigger}
        disabled={isBusy}
        className={cn(
          'rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
          isBusy
            ? 'cursor-not-allowed bg-stone-100 text-stone-400 dark:bg-stone-800'
            : 'bg-brand text-white hover:bg-brand-dark',
        )}
      >
        {loading ? 'Queuing…' : isBusy ? 'Syncing…' : 'Sync now'}
      </button>
    </div>
  )
}
