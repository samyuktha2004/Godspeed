import { useQuery } from '@tanstack/react-query'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip,
} from 'recharts'
import { apiFetch } from '@/lib/http'
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton'
import { cn } from '@/lib/utils'

interface DomainScore {
  domain:    string
  coverage:  number
  freshness: number
  accuracy:  number
  score:     number
}

interface HealthResponse {
  overall_score: number
  domains:       DomainScore[]
}

async function fetchHealth(): Promise<HealthResponse> {
  const res = await apiFetch('/api/analytics/knowledge-health')
  return res.json()
}

function ScoreBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const colour =
    pct >= 80 ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' :
    pct >= 60 ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400' :
                'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
  return (
    <span className={cn('rounded-full px-2 py-0.5 text-xs font-semibold', colour)}>
      {pct}%
    </span>
  )
}

function HeatCell({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const bg =
    pct >= 80 ? 'bg-green-500' :
    pct >= 60 ? 'bg-amber-400' :
    pct >= 40 ? 'bg-orange-400' : 'bg-red-500'
  return (
    <td className="px-2 py-2 text-center">
      <div
        className={cn('mx-auto h-8 w-16 rounded flex items-center justify-center text-xs font-medium text-white', bg)}
        title={`${pct}%`}
      >
        {pct}%
      </div>
    </td>
  )
}

export function KnowledgeHealthDashboard() {
  const { data, isLoading } = useQuery({
    queryKey: ['analytics-knowledge-health'],
    queryFn:  fetchHealth,
    staleTime: 300_000,
  })

  const overall = data ? Math.round(data.overall_score * 100) : 0
  const radarData = data?.domains.map((d) => ({
    domain:    d.domain,
    Coverage:  Math.round(d.coverage  * 100),
    Freshness: Math.round(d.freshness * 100),
    Accuracy:  Math.round(d.accuracy  * 100),
  })) ?? []

  return (
    <div className="flex flex-col gap-6">
      {/* Overall score */}
      <div className="rounded-xl border border-surface-subtle p-5">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-stone-500">Overall Knowledge Health</p>
            {isLoading ? (
              <div className="mt-1 h-8 w-20 animate-pulse rounded bg-stone-200 dark:bg-stone-700" />
            ) : (
              <p className={cn(
                'text-4xl font-bold',
                overall >= 80 ? 'text-green-600' :
                overall >= 60 ? 'text-amber-500' : 'text-red-500',
              )}>
                {overall}%
              </p>
            )}
          </div>
          {!isLoading && (
            <div className="text-right text-sm text-stone-400">
              <p>{data?.domains.length ?? 0} domains tracked</p>
            </div>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Radar chart */}
        <div className="rounded-xl border border-surface-subtle p-5">
          <p className="mb-4 text-sm font-medium text-stone-500">Coverage / Freshness / Accuracy</p>
          {isLoading ? (
            <LoadingSkeleton rows={4} />
          ) : (
            <ResponsiveContainer width="100%" height={240}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="#e7e5e4" />
                <PolarAngleAxis dataKey="domain" tick={{ fontSize: 11 }} />
                <Tooltip />
                <Radar name="Coverage"  dataKey="Coverage"  stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.15} />
                <Radar name="Freshness" dataKey="Freshness" stroke="#22c55e" fill="#22c55e" fillOpacity={0.15} />
                <Radar name="Accuracy"  dataKey="Accuracy"  stroke="#f59e0b" fill="#f59e0b" fillOpacity={0.15} />
              </RadarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Heatmap table */}
        <div className="rounded-xl border border-surface-subtle p-5">
          <p className="mb-4 text-sm font-medium text-stone-500">Domain Breakdown</p>
          {isLoading ? (
            <LoadingSkeleton rows={4} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-surface-subtle text-xs text-stone-400">
                    <th className="py-2 text-left font-medium">Domain</th>
                    <th className="px-2 py-2 text-center font-medium">Coverage</th>
                    <th className="px-2 py-2 text-center font-medium">Freshness</th>
                    <th className="px-2 py-2 text-center font-medium">Accuracy</th>
                    <th className="px-2 py-2 text-center font-medium">Score</th>
                  </tr>
                </thead>
                <tbody>
                  {(data?.domains ?? []).map((d) => (
                    <tr key={d.domain} className="border-b border-surface-subtle/50 last:border-0">
                      <td className="py-2 font-medium">{d.domain}</td>
                      <HeatCell value={d.coverage}  />
                      <HeatCell value={d.freshness} />
                      <HeatCell value={d.accuracy}  />
                      <td className="px-2 py-2 text-center">
                        <ScoreBadge value={d.score} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
