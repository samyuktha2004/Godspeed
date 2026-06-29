import { useQuery } from '@tanstack/react-query'
import { RadialBarChart, RadialBar, ResponsiveContainer } from 'recharts'
import { apiFetch } from '@/lib/http'
import { cn } from '@/lib/utils'

async function fetchRate(teamId: string | null | undefined): Promise<{ success_rate: number; unique_users: number; avg_response_time_ms: number }> {
  const params = new URLSearchParams({ date_range: '30d' })
  if (teamId) params.set('team_id', teamId)
  const res = await apiFetch(`/api/analytics/queries?${params}`)
  return res.json()
}

export function SuccessRateGauge({ teamId }: { teamId?: string | null }) {
  const { data, isLoading } = useQuery({
    queryKey: ['analytics-trend', teamId ?? 'all'],
    queryFn: () => fetchRate(teamId),
    staleTime: 300_000,
  })

  const rate   = data?.success_rate ?? 0
  const pct    = Math.round(rate * 100)
  const colour = pct >= 80 ? '#22c55e' : pct >= 60 ? '#f59e0b' : '#ef4444'

  return (
    <div className="rounded-xl border border-surface-subtle p-5">
      <p className="mb-1 text-sm font-medium text-stone-500">Success Rate</p>
      <div className="flex items-center gap-6">
        <div className="relative h-24 w-24">
          {!isLoading && (
            <ResponsiveContainer width="100%" height="100%">
              <RadialBarChart innerRadius="70%" outerRadius="100%" data={[{ value: pct, fill: colour }]} startAngle={90} endAngle={90 - (pct / 100) * 360}>
                <RadialBar dataKey="value" cornerRadius={4} />
              </RadialBarChart>
            </ResponsiveContainer>
          )}
          <span className={cn('absolute inset-0 flex items-center justify-center text-xl font-bold', isLoading && 'text-stone-300')}>
            {isLoading ? '—' : `${pct}%`}
          </span>
        </div>
        <div className="flex flex-col gap-2 text-sm">
          <div>
            <p className="text-stone-500">Avg response</p>
            <p className="font-semibold">{isLoading ? '—' : `${((data?.avg_response_time_ms ?? 0) / 1000).toFixed(1)}s`}</p>
          </div>
          <div>
            <p className="text-stone-500">Unique users</p>
            <p className="font-semibold">{isLoading ? '—' : (data?.unique_users ?? 0)}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
