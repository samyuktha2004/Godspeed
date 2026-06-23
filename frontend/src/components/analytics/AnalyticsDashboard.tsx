import { useState } from 'react'
import { Tabs, TabPanel } from '@/components/common/Tabs'
import { QueryTrendChart } from './QueryTrendChart'
import { TopicsBarChart } from './TopicsBarChart'
import { SuccessRateGauge } from './SuccessRateGauge'
import { KnowledgeHealthDashboard } from './KnowledgeHealthDashboard'
import { DependencyTracker } from './DependencyTracker'
import { EscalationTable } from './EscalationTable'
import { AnalyticsExport } from './AnalyticsExport'

type Tab = 'overview' | 'health' | 'dependencies' | 'escalations' | 'export'

const TABS = [
  { id: 'overview'     as const, label: 'Overview'          },
  { id: 'health'       as const, label: 'Knowledge Health'  },
  { id: 'dependencies' as const, label: 'Dependencies'      },
  { id: 'escalations'  as const, label: 'Escalations'       },
  { id: 'export'       as const, label: 'Export'            },
]

export function AnalyticsDashboard() {
  const [tab, setTab] = useState<Tab>('overview')

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-semibold">Analytics</h1>

      <Tabs tabs={TABS} active={tab} onChange={setTab} className="mb-6" />

      <TabPanel id="overview" active={tab}>
        <div className="flex flex-col gap-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <QueryTrendChart />
            <SuccessRateGauge />
          </div>
          <TopicsBarChart />
        </div>
      </TabPanel>

      <TabPanel id="health"       active={tab}><KnowledgeHealthDashboard /></TabPanel>
      <TabPanel id="dependencies" active={tab}><DependencyTracker /></TabPanel>
      <TabPanel id="escalations"  active={tab}><EscalationTable /></TabPanel>
      <TabPanel id="export"       active={tab}><AnalyticsExport /></TabPanel>
    </div>
  )
}
