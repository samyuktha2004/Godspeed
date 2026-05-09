import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { apiFetch } from '@/lib/http'
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton'

interface Topic { topic: string; count: number }

async function fetchTopics(): Promise<{ topics: Topic[] }> {
  const res = await apiFetch('/api/analytics/topics?limit=10')
  return res.json()
}

export function TopicsBarChart() {
  const { data, isLoading } = useQuery({ queryKey: ['analytics-topics'], queryFn: fetchTopics, staleTime: 300_000 })

  return (
    <div className="rounded-xl border border-surface-subtle p-5">
      <p className="mb-4 text-sm font-medium text-stone-500">Top Query Topics</p>
      {isLoading ? (
        <LoadingSkeleton rows={3} />
      ) : (
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data?.topics ?? []} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="#e7e5e4" horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 10 }} />
            <YAxis type="category" dataKey="topic" tick={{ fontSize: 11 }} width={140} />
            <Tooltip />
            <Bar dataKey="count" fill="#b45309" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
