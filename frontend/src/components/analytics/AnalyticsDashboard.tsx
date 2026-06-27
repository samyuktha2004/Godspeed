import { useState } from 'react'
import { Tabs, TabPanel } from '@/components/common/Tabs'
import { QueryTrendChart } from './QueryTrendChart'
import { TopicsBarChart } from './TopicsBarChart'
import { SuccessRateGauge } from './SuccessRateGauge'
import { KnowledgeHealthDashboard } from './KnowledgeHealthDashboard'
import { DependencyTracker } from './DependencyTracker'
import { EscalationTable } from './EscalationTable'
import { AnalyticsExport } from './AnalyticsExport'
import { useAuth } from '@/hooks/useAuth'
import { usePermissions } from '@/hooks/usePermissions'
import { Permission } from '@/lib/permissions'

type Tab = 'overview' | 'health' | 'dependencies' | 'escalations' | 'export'

const BASE_TABS = [
  { id: 'overview'     as const, label: 'Overview'          },
  { id: 'health'       as const, label: 'Knowledge Health'  },
  { id: 'dependencies' as const, label: 'Dependencies'      },
  { id: 'escalations'  as const, label: 'Escalations'       },
]
const EXPORT_TAB = { id: 'export' as const, label: 'Export' }

export function AnalyticsDashboard() {
  const [tab, setTab] = useState<Tab>('overview')
  const { user } = useAuth()
  const { can } = usePermissions()
  const canExport  = can(Permission.EXPORT_ANALYTICS)
  const teamId     = can(Permission.VIEW_ANY_ANALYTICS) ? null : (user?.team_id ?? null)
  const tabs       = canExport ? [...BASE_TABS, EXPORT_TAB] : BASE_TABS

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-semibold">Analytics</h1>

      <Tabs tabs={tabs} active={tab} onChange={setTab} className="mb-6" />

      <TabPanel id="overview" active={tab}>
        <div className="flex flex-col gap-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <QueryTrendChart teamId={teamId} />
            <SuccessRateGauge teamId={teamId} />
          </div>
          <TopicsBarChart />
        </div>
      </TabPanel>

      <TabPanel id="health"       active={tab}><KnowledgeHealthDashboard /></TabPanel>
      <TabPanel id="dependencies" active={tab}><DependencyTracker /></TabPanel>
      <TabPanel id="escalations"  active={tab}><EscalationTable teamId={teamId} /></TabPanel>
      {canExport && (
        <TabPanel id="export" active={tab}><AnalyticsExport teamId={teamId} /></TabPanel>
      )}
    </div>
  )
}
