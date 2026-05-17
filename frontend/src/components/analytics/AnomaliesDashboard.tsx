import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '@/lib/http'
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton'
import { cn } from '@/lib/utils'
import { useAuthStore } from '@/stores/authStore'
import { QuerySpikeChart } from './QuerySpikeChart'
import { EscalationTrendChart } from './EscalationTrendChart'
import { StalenessRiskList } from './StalenessRiskList'
import type { AnomalySignal, SignalsSummary, SignalsResponse } from '@/types/anomaly'

async function fetchSummary(): Promise<SignalsSummary> {
  const res = await apiFetch('/api/anomaly/signals/summary')
  return res.json()
}

async function fetchSignals(): Promise<SignalsResponse> {
  const res = await apiFetch('/api/anomaly/signals?resolved=false&limit=50')
  return res.json()
}

async function resolveSignal(signalId: string): Promise<void> {
  await apiFetch(`/api/anomaly/signals/${signalId}/resolve`, { method: 'PATCH' })
}

const SEVERITY_STYLES = {
  critical: {
    badge: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    dot:   'bg-red-500',
    count: 'bg-red-50 text-red-700 dark:bg-red-900/20 dark:text-red-300',
  },
  high: {
    badge: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
    dot:   'bg-orange-500',
    count: 'bg-orange-50 text-orange-700 dark:bg-orange-900/20 dark:text-orange-300',
  },
  medium: {
    badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
    dot:   'bg-amber-500',
    count: 'bg-amber-50 text-amber-700 dark:bg-amber-900/20 dark:text-amber-300',
  },
  low: {
    badge: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    dot:   'bg-green-500',
    count: 'bg-green-50 text-green-700 dark:bg-green-900/20 dark:text-green-300',
  },
} as const

const SIGNAL_LABELS: Record<string, string> = {
  query_spike:      'Query Spike',
  query_drop:       'Query Drop',
  escalation_trend: 'Escalation Trend',
  staleness:        'Staleness',
  dependency_risk:  'Dependency Risk',
}

function SeverityBadge({ severity }: { severity: string }) {
  const s = SEVERITY_STYLES[severity as keyof typeof SEVERITY_STYLES] ?? SEVERITY_STYLES.low
  return (
    <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium capitalize', s.badge)}>
      {severity}
    </span>
  )
}

function SignalCard({
  signal,
  canResolve,
  onResolve,
}: {
  signal:     AnomalySignal
  canResolve: boolean
  onResolve:  (id: string) => void
}) {
  const s = SEVERITY_STYLES[signal.severity] ?? SEVERITY_STYLES.low
  return (
    <div className="flex items-start gap-3 rounded-lg border border-surface-subtle p-3 hover:bg-stone-50 dark:hover:bg-stone-900/20">
      <div className={cn('mt-1.5 h-2 w-2 shrink-0 rounded-full', s.dot)} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <SeverityBadge severity={signal.severity} />
          <span className="text-xs font-medium text-stone-700 dark:text-stone-300">
            {SIGNAL_LABELS[signal.signal_type] ?? signal.signal_type}
          </span>
          {signal.entity_id && (
            <span className="text-xs text-stone-400">{signal.entity_id}</span>
          )}
        </div>
        <p className="mt-0.5 text-xs text-stone-400">
          Score: {signal.score.toFixed(3)} · {new Date(signal.detected_at).toLocaleString()}
        </p>
      </div>
      {canResolve && (
        <button
          onClick={() => onResolve(signal.id)}
          className="shrink-0 rounded-md border border-stone-200 px-2 py-1 text-xs text-stone-500 transition-colors hover:border-brand hover:text-brand dark:border-stone-700"
        >
          Resolve
        </button>
      )}
    </div>
  )
}

export function AnomaliesDashboard() {
  const user        = useAuthStore((s) => s.user)
  const isAdmin     = user?.role === 'admin' || user?.role === 'org_admin'
  const queryClient = useQueryClient()

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey:        ['anomaly-summary'],
    queryFn:         fetchSummary,
    staleTime:       120_000,
    refetchInterval: 120_000,
  })

  const { data: signalsData, isLoading: signalsLoading } = useQuery({
    queryKey:        ['anomaly-signals'],
    queryFn:         fetchSignals,
    staleTime:       120_000,
    refetchInterval: 120_000,
  })

  const { mutate: resolve } = useMutation({
    mutationFn: resolveSignal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['anomaly-signals'] })
      queryClient.invalidateQueries({ queryKey: ['anomaly-summary'] })
    },
  })

  const signals = signalsData?.signals ?? []

  return (
    <div className="flex flex-col gap-6">

      {/* Severity Summary */}
      <div className="rounded-xl border border-surface-subtle p-5">
        <p className="mb-3 text-sm font-medium text-stone-500">Signal Summary</p>
        {summaryLoading ? (
          <LoadingSkeleton rows={1} />
        ) : (
          <div className="flex flex-wrap gap-3">
            {(['critical', 'high', 'medium', 'low'] as const).map((sev) => {
              const count = summary?.by_severity?.[sev] ?? 0
              const s = SEVERITY_STYLES[sev]
              return (
                <div
                  key={sev}
                  className={cn(
                    'flex items-center gap-2 rounded-lg border px-4 py-2',
                    count > 0 ? s.count : 'border-stone-100 bg-stone-50 dark:border-stone-800 dark:bg-stone-900/20',
                  )}
                >
                  <div className={cn('h-2 w-2 rounded-full', s.dot)} />
                  <span className="text-sm font-semibold tabular-nums">{count}</span>
                  <span className="text-xs capitalize text-stone-500">{sev}</span>
                </div>
              )
            })}
            <div className="flex items-center gap-2 rounded-lg border border-stone-100 bg-stone-50 px-4 py-2 dark:border-stone-800 dark:bg-stone-900/20">
              <span className="text-sm font-semibold tabular-nums text-stone-700 dark:text-stone-200">
                {summary?.total ?? 0}
              </span>
              <span className="text-xs text-stone-500">total unresolved</span>
            </div>
          </div>
        )}
      </div>

      {/* Active Alerts Feed */}
      <div className="rounded-xl border border-surface-subtle p-5">
        <div className="mb-3 flex items-center gap-2">
          <p className="text-sm font-medium text-stone-500">Active Alerts</p>
          {signals.length > 0 && (
            <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700 dark:bg-red-900/30 dark:text-red-400">
              {signals.length}
            </span>
          )}
          <span className="ml-auto text-xs text-stone-400">auto-refreshes every 2 min</span>
        </div>

        {signalsLoading ? (
          <LoadingSkeleton rows={4} />
        ) : signals.length === 0 ? (
          <div className="py-10 text-center">
            <p className="text-2xl">✓</p>
            <p className="mt-2 text-sm font-medium text-stone-500">No active anomaly signals</p>
            <p className="mt-0.5 text-xs text-stone-400">
              Detection runs every 15 min (query spikes) and daily 03:00 UTC (staleness, dependency risk)
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {signals.map((s) => (
              <SignalCard
                key={s.id}
                signal={s}
                canResolve={isAdmin}
                onResolve={resolve}
              />
            ))}
          </div>
        )}
      </div>

      {/* Charts */}
      <QuerySpikeChart />
      <EscalationTrendChart />
      <StalenessRiskList />

      {/* Dependency risk note */}
      <div className="rounded-xl border border-surface-subtle bg-stone-50 p-4 text-xs text-stone-500 dark:bg-stone-900/30">
        <span className="font-medium text-stone-700 dark:text-stone-300">Dependency risk scores</span>
        {' '}are available in the{' '}
        <strong>Dependencies</strong> tab — each library now includes a Risk Score badge and 30-day incident probability.
      </div>
    </div>
  )
}
