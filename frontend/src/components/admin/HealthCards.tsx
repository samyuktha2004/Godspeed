import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/lib/http'
import { cn } from '@/lib/utils'

interface HealthResponse {
  status:  'ok' | 'degraded'
  neo4j:   string
  redis:   string
  qdrant:  string
}

const SERVICES: Array<{ key: keyof Omit<HealthResponse, 'status'>; label: string }> = [
  { key: 'neo4j',  label: 'Neo4j'  },
  { key: 'redis',  label: 'Redis'  },
  { key: 'qdrant', label: 'Qdrant' },
]

async function fetchHealth(): Promise<HealthResponse> {
  const res = await apiFetch('/health')
  return res.json()
}

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={cn(
        'inline-block h-2.5 w-2.5 rounded-full',
        ok ? 'bg-green-500' : 'bg-red-500',
      )}
      aria-hidden
    />
  )
}

export function HealthCards() {
  const { data, isLoading, isError } = useQuery({
    queryKey:        ['health'],
    queryFn:         fetchHealth,
    refetchInterval: 30_000,
    retry:           1,
  })

  const degraded = data?.status === 'degraded'

  return (
    <div className="flex flex-col gap-4">
      {degraded && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700 dark:border-red-800 dark:bg-red-950/30 dark:text-red-400">
          ⚠ One or more services are degraded — some features may not work correctly.
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {/* API card — if we got a response, API is up */}
        <div className="flex items-center gap-3 rounded-lg border border-surface-subtle p-4">
          <StatusDot ok={!isError} />
          <div>
            <p className="text-xs font-medium text-stone-500">API</p>
            <p className="text-sm font-semibold">{isError ? 'Error' : isLoading ? '…' : 'OK'}</p>
          </div>
        </div>

        {SERVICES.map(({ key, label }) => {
          const val = data?.[key] ?? ''
          const ok  = val === 'ok'
          return (
            <div key={key} className="flex items-center gap-3 rounded-lg border border-surface-subtle p-4">
              <StatusDot ok={ok} />
              <div className="min-w-0">
                <p className="text-xs font-medium text-stone-500">{label}</p>
                <p className={cn('truncate text-sm font-semibold', !ok && 'text-red-600 dark:text-red-400')}>
                  {isLoading ? '…' : ok ? 'OK' : (val.replace('error: ', '') || 'Error')}
                </p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
