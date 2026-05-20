import { useState, useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/lib/http'
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton'
import { cn } from '@/lib/utils'

interface HistoryItem {
  id:           string
  query:        string
  answer_brief: string
  created_at:   string
  success:      boolean
  duration_ms:  number
}

interface HistoryResponse {
  items: HistoryItem[]
  total: number
}

async function fetchHistory(page: number): Promise<HistoryResponse> {
  const res = await apiFetch(`/api/workspace/history?page=${page}&limit=20`)
  return res.json()
}

interface Props {
  onReplay?: (query: string) => void
  focusId?:  string
}

export function QueryHistory({ onReplay, focusId }: Props) {
  const [page,     setPage]     = useState(1)
  const [expanded, setExpanded] = useState<string | null>(focusId ?? null)
  const focusRef = useRef<HTMLDivElement>(null)

  const { data, isLoading } = useQuery({
    queryKey:  ['workspace-history', page],
    queryFn:   () => fetchHistory(page),
    staleTime: 60_000,
  })

  // Scroll the focused item into view once data loads
  useEffect(() => {
    if (focusId && focusRef.current) {
      focusRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }
  }, [focusId, data])

  const totalPages = data ? Math.ceil(data.total / 20) : 1

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-stone-500">Query History</p>
        {data && (
          <p className="text-xs text-stone-400">{data.total} total queries</p>
        )}
      </div>

      {isLoading ? (
        <div className="rounded-xl border border-surface-subtle p-5">
          <LoadingSkeleton rows={5} />
        </div>
      ) : (data?.items ?? []).length === 0 ? (
        <div className="rounded-xl border border-dashed border-surface-subtle py-16 text-center">
          <p className="text-sm text-stone-400">No queries yet. Ask something to get started.</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {(data?.items ?? []).map((item) => (
            <div
              key={item.id}
              ref={item.id === focusId ? focusRef : undefined}
              className={cn(
                'rounded-xl border border-surface-subtle transition-colors hover:border-stone-300 dark:hover:border-stone-600',
                item.id === focusId && 'border-brand/50 dark:border-brand/40',
              )}
            >
              <button
                className="flex w-full items-start gap-3 p-4 text-left"
                onClick={() => setExpanded(expanded === item.id ? null : item.id)}
              >
                <span
                  className={cn(
                    'mt-1 h-2 w-2 flex-shrink-0 rounded-full',
                    item.success ? 'bg-green-500' : 'bg-red-400',
                  )}
                  aria-label={item.success ? 'successful' : 'failed'}
                />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{item.query}</p>
                  <p className="mt-0.5 text-xs text-stone-400">
                    {new Date(item.created_at).toLocaleString()} · {(item.duration_ms / 1000).toFixed(1)}s
                  </p>
                </div>
                <svg
                  className={cn('h-4 w-4 flex-shrink-0 text-stone-400 transition-transform', expanded === item.id && 'rotate-180')}
                  viewBox="0 0 20 20"
                  fill="currentColor"
                >
                  <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
              </button>

              {expanded === item.id && (
                <div className="border-t border-surface-subtle px-4 pb-4 pt-3">
                  <p className="text-sm text-stone-600 dark:text-stone-400">{item.answer_brief}</p>
                  {onReplay && (
                    <button
                      onClick={() => onReplay(item.query)}
                      className="mt-3 text-xs font-medium text-brand hover:underline"
                    >
                      Ask again →
                    </button>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="rounded-lg border border-surface-subtle px-3 py-1.5 text-xs font-medium disabled:opacity-40"
          >
            ← Previous
          </button>
          <span className="text-xs text-stone-500">Page {page} of {totalPages}</span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="rounded-lg border border-surface-subtle px-3 py-1.5 text-xs font-medium disabled:opacity-40"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  )
}
