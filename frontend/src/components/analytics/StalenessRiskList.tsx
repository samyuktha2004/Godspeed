import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'
import { apiFetch } from '@/lib/http'
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton'
import type { StalenessDoc, StalenessResponse } from '@/types/anomaly'

async function fetchStaleness(): Promise<StalenessResponse> {
  const res = await apiFetch('/api/anomaly/staleness?limit=20')
  return res.json()
}

function barColor(score: number): string {
  if (score >= 0.8) return '#ef4444'
  if (score >= 0.6) return '#f97316'
  if (score >= 0.3) return '#f59e0b'
  return '#22c55e'
}

interface TooltipProps {
  active?:  boolean
  payload?: { payload: StalenessDoc & { title: string } }[]
}

function StalenessTooltip({ active, payload }: TooltipProps) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="rounded-lg border border-surface-subtle bg-white p-3 text-xs shadow dark:bg-stone-900">
      <p className="mb-1.5 max-w-[200px] font-medium leading-tight">{d.details.title}</p>
      <p className="text-stone-500">Age: {d.details.age_days} days</p>
      <p className="text-stone-500">Age factor: {(d.details.age_factor * 100).toFixed(0)}%</p>
      <p className="text-stone-500">Query pressure: {(d.details.query_pressure * 100).toFixed(0)}%</p>
      <p className="mt-1.5 font-semibold text-stone-700 dark:text-stone-200">
        Risk score: {(d.score * 100).toFixed(0)}%
      </p>
    </div>
  )
}

export function StalenessRiskList() {
  const { data, isLoading } = useQuery({
    queryKey:  ['anomaly-staleness'],
    queryFn:   fetchStaleness,
    staleTime: 300_000,
  })

  const rawDocs = data?.documents ?? []
  // Flatten nested title so Recharts YAxis can use it as a category key
  const docs = rawDocs.map((d) => ({ ...d, title: d.details.title }))

  return (
    <div className="rounded-xl border border-surface-subtle p-5">
      <p className="mb-4 text-sm font-medium text-stone-500">Document Staleness Risk (top 20)</p>

      {isLoading ? (
        <LoadingSkeleton rows={5} />
      ) : docs.length === 0 ? (
        <p className="py-8 text-center text-sm text-stone-400">
          No staleness data yet — detection runs daily at 03:00 UTC.
        </p>
      ) : (
        <ResponsiveContainer width="100%" height={Math.max(200, docs.length * 30)}>
          <BarChart
            layout="vertical"
            data={docs}
            margin={{ top: 0, right: 48, left: 8, bottom: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e5e7eb" />
            <XAxis
              type="number"
              domain={[0, 1]}
              tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
              tick={{ fontSize: 10 }}
            />
            <YAxis
              type="category"
              dataKey="title"
              width={160}
              tick={{ fontSize: 10 }}
              tickFormatter={(v: string) => (v.length > 22 ? `${v.slice(0, 22)}…` : v)}
            />
            <Tooltip content={<StalenessTooltip />} />
            <Bar dataKey="score" radius={[0, 3, 3, 0]}>
              {docs.map((d) => (
                <Cell key={d.entity_id} fill={barColor(d.score)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
