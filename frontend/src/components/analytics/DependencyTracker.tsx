import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/lib/http'
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton'
import { cn } from '@/lib/utils'

interface Dependency {
  name:            string
  type:            'service' | 'library' | 'infra'
  current_version: string
  latest_version:  string
  breaking_change: boolean
  teams:           string[]
  last_checked:    string
}

interface DepResponse {
  dependencies: Dependency[]
}

async function fetchDeps(): Promise<DepResponse> {
  const res = await apiFetch('/api/analytics/dependencies')
  return res.json()
}

type SortKey = 'name' | 'type' | 'breaking_change'

function VersionBadge({ current, latest, breaking }: { current: string; latest: string; breaking: boolean }) {
  const upToDate = current === latest
  if (upToDate) {
    return (
      <span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900/30 dark:text-green-400">
        up to date
      </span>
    )
  }
  return (
    <div className="flex items-center gap-1.5 text-xs">
      <span className="text-stone-500 line-through">{current}</span>
      <span>→</span>
      <span className={cn(
        'rounded-full px-2 py-0.5 font-medium',
        breaking
          ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
          : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
      )}>
        {latest}
      </span>
    </div>
  )
}

const TYPE_COLOURS: Record<Dependency['type'], string> = {
  service: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  library: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  infra:   'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300',
}

export function DependencyTracker() {
  const { data, isLoading } = useQuery({
    queryKey:  ['analytics-deps'],
    queryFn:   fetchDeps,
    staleTime: 300_000,
  })

  const [sort, setSort]     = useState<SortKey>('breaking_change')
  const [filter, setFilter] = useState<'all' | 'outdated' | 'breaking'>('all')

  const deps = (data?.dependencies ?? [])
    .filter((d) => {
      if (filter === 'outdated') return d.current_version !== d.latest_version
      if (filter === 'breaking') return d.breaking_change
      return true
    })
    .sort((a, b) => {
      if (sort === 'breaking_change') return (b.breaking_change ? 1 : 0) - (a.breaking_change ? 1 : 0)
      if (sort === 'type')            return a.type.localeCompare(b.type)
      return a.name.localeCompare(b.name)
    })

  const breakingCount = (data?.dependencies ?? []).filter((d) => d.breaking_change).length

  return (
    <div className="rounded-xl border border-surface-subtle p-5">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-stone-500">Dependency Tracker</p>
          {breakingCount > 0 && (
            <p className="mt-0.5 text-xs text-red-600 dark:text-red-400">
              {breakingCount} breaking change{breakingCount > 1 ? 's' : ''} require attention
            </p>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Filter buttons */}
          <div className="flex rounded-lg border border-surface-subtle text-xs">
            {(['all', 'outdated', 'breaking'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={cn(
                  'px-3 py-1.5 capitalize transition-colors first:rounded-l-lg last:rounded-r-lg',
                  filter === f
                    ? 'bg-brand text-white'
                    : 'text-stone-500 hover:text-stone-700',
                )}
              >
                {f}
              </button>
            ))}
          </div>

          {/* Sort */}
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            className="rounded-lg border border-surface-subtle bg-white px-2 py-1.5 text-xs text-stone-600 dark:bg-stone-900 dark:text-stone-300"
          >
            <option value="breaking_change">Sort: Breaking first</option>
            <option value="type">Sort: Type</option>
            <option value="name">Sort: Name</option>
          </select>
        </div>
      </div>

      {isLoading ? (
        <LoadingSkeleton rows={5} />
      ) : deps.length === 0 ? (
        <p className="py-8 text-center text-sm text-stone-400">No dependencies match this filter.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-subtle text-xs text-stone-400">
                <th className="py-2 text-left font-medium">Dependency</th>
                <th className="px-3 py-2 text-left font-medium">Type</th>
                <th className="px-3 py-2 text-left font-medium">Version</th>
                <th className="px-3 py-2 text-left font-medium">Teams</th>
                <th className="px-3 py-2 text-left font-medium">Checked</th>
              </tr>
            </thead>
            <tbody>
              {deps.map((d) => (
                <tr key={d.name} className="border-b border-surface-subtle/50 last:border-0 hover:bg-stone-50 dark:hover:bg-stone-900/30">
                  <td className="py-2.5 font-medium">
                    <div className="flex items-center gap-2">
                      {d.breaking_change && (
                        <span className="h-1.5 w-1.5 rounded-full bg-red-500" aria-label="breaking change" />
                      )}
                      {d.name}
                    </div>
                  </td>
                  <td className="px-3 py-2.5">
                    <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium capitalize', TYPE_COLOURS[d.type])}>
                      {d.type}
                    </span>
                  </td>
                  <td className="px-3 py-2.5">
                    <VersionBadge current={d.current_version} latest={d.latest_version} breaking={d.breaking_change} />
                  </td>
                  <td className="px-3 py-2.5 text-stone-500">
                    {d.teams.slice(0, 2).join(', ')}{d.teams.length > 2 ? ` +${d.teams.length - 2}` : ''}
                  </td>
                  <td className="px-3 py-2.5 text-stone-400 text-xs">
                    {new Date(d.last_checked).toLocaleDateString()}
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
