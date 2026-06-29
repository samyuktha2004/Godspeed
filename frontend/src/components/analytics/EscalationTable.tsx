import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/lib/http'
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton'
import { cn } from '@/lib/utils'

interface Escalation {
  id:            string
  query:         string
  frequency:     number
  last_seen:     string
  teams:         string[]
  status:        'open' | 'in_progress' | 'resolved'
  gap_type:      'missing_knowledge' | 'stale_content' | 'incorrect_answer' | 'out_of_scope'
}

interface EscalationResponse {
  escalations: Escalation[]
  total:        number
}

async function fetchEscalations(teamId: string | null | undefined): Promise<EscalationResponse> {
  const params = new URLSearchParams({ limit: '50' })
  if (teamId) params.set('team_id', teamId)
  const res = await apiFetch(`/api/analytics/escalations?${params}`)
  return res.json()
}

const STATUS_STYLES: Record<Escalation['status'], string> = {
  open:        'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  in_progress: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  resolved:    'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
}

const GAP_LABELS: Record<Escalation['gap_type'], string> = {
  missing_knowledge: 'Missing knowledge',
  stale_content:     'Stale content',
  incorrect_answer:  'Incorrect answer',
  out_of_scope:      'Out of scope',
}

export function EscalationTable({ teamId }: { teamId?: string | null }) {
  const { data, isLoading } = useQuery({
    queryKey:  ['analytics-escalations', teamId ?? 'all'],
    queryFn:   () => fetchEscalations(teamId),
    staleTime: 120_000,
  })

  const [statusFilter, setStatusFilter] = useState<'all' | Escalation['status']>('open')

  const rows = (data?.escalations ?? []).filter(
    (e) => statusFilter === 'all' || e.status === statusFilter,
  )

  return (
    <div className="rounded-xl border border-surface-subtle p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-stone-500">Unresolved Escalations</p>
          <p className="mt-0.5 text-xs text-stone-400">
            Queries that couldn't be answered — sorted by frequency
          </p>
        </div>

        <div className="flex rounded-lg border border-surface-subtle text-xs">
          {(['all', 'open', 'in_progress', 'resolved'] as const).map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={cn(
                'px-3 py-1.5 transition-colors first:rounded-l-lg last:rounded-r-lg',
                statusFilter === s
                  ? 'bg-brand text-white'
                  : 'text-stone-500 hover:text-stone-700',
              )}
            >
              {s === 'in_progress' ? 'In Progress' : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <LoadingSkeleton rows={5} />
      ) : rows.length === 0 ? (
        <div className="py-12 text-center">
          <p className="text-2xl">✓</p>
          <p className="mt-2 text-sm font-medium text-stone-500">No escalations in this category</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-subtle text-xs text-stone-400">
                <th className="py-2 text-left font-medium">Query</th>
                <th className="px-3 py-2 text-right font-medium">Freq</th>
                <th className="px-3 py-2 text-left font-medium">Gap type</th>
                <th className="px-3 py-2 text-left font-medium">Teams</th>
                <th className="px-3 py-2 text-left font-medium">Status</th>
                <th className="px-3 py-2 text-left font-medium">Last seen</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => (
                <tr
                  key={e.id}
                  className="border-b border-surface-subtle/50 last:border-0 hover:bg-stone-50 dark:hover:bg-stone-900/30"
                >
                  <td className="max-w-xs py-3">
                    <p className="truncate font-medium" title={e.query}>{e.query}</p>
                  </td>
                  <td className="px-3 py-3 text-right font-semibold tabular-nums">{e.frequency}</td>
                  <td className="px-3 py-3 text-xs text-stone-500">{GAP_LABELS[e.gap_type]}</td>
                  <td className="px-3 py-3 text-xs text-stone-500">
                    {e.teams.slice(0, 2).join(', ')}{e.teams.length > 2 ? ` +${e.teams.length - 2}` : ''}
                  </td>
                  <td className="px-3 py-3">
                    <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium capitalize', STATUS_STYLES[e.status])}>
                      {e.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-xs text-stone-400">
                    {new Date(e.last_seen).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
