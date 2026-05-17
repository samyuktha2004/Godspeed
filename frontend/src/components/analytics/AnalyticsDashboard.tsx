import { useState } from 'react'
import { QueryTrendChart } from './QueryTrendChart'
import { TopicsBarChart } from './TopicsBarChart'
import { SuccessRateGauge } from './SuccessRateGauge'
import { KnowledgeHealthDashboard } from './KnowledgeHealthDashboard'
import { DependencyTracker } from './DependencyTracker'
import { EscalationTable } from './EscalationTable'
import { AnalyticsExport } from './AnalyticsExport'
import { AnomaliesDashboard } from './AnomaliesDashboard'

type Tab = 'overview' | 'health' | 'dependencies' | 'escalations' | 'export' | 'anomalies'

const TABS: { id: Tab; label: string }[] = [
  { id: 'overview',     label: 'Overview' },
  { id: 'health',       label: 'Knowledge Health' },
  { id: 'dependencies', label: 'Dependencies' },
  { id: 'escalations',  label: 'Escalations' },
  { id: 'export',       label: 'Export' },
  { id: 'anomalies',    label: 'Anomalies' },
]

export function AnalyticsDashboard() {
  const [tab, setTab] = useState<Tab>('overview')

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-semibold">Analytics</h1>

      {/* Tab bar */}
      <div className="mb-6 flex gap-1 overflow-x-auto border-b border-surface-subtle">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`whitespace-nowrap px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.id
                ? 'border-b-2 border-brand text-brand'
                : 'text-stone-500 hover:text-stone-700 dark:hover:text-stone-300'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="flex flex-col gap-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <QueryTrendChart />
            <SuccessRateGauge />
          </div>
          <TopicsBarChart />
        </div>
      )}

      {tab === 'health'       && <KnowledgeHealthDashboard />}
      {tab === 'dependencies' && <DependencyTracker />}
      {tab === 'escalations'  && <EscalationTable />}
      {tab === 'export'       && <AnalyticsExport />}
      {tab === 'anomalies'    && <AnomaliesDashboard />}
    </div>
  )
}
