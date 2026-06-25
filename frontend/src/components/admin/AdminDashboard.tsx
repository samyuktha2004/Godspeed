import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Tabs, TabPanel } from '@/components/common/Tabs'
import { HealthCards } from './HealthCards'
import { SyncTrigger } from './SyncTrigger'
import { GraphIngestButton } from './GraphIngestButton'
import { FileUploadWidget } from './FileUploadWidget'
import { DataSourceManager } from './DataSourceManager'
import { SystemLogs } from './SystemLogs'
import { AdminUserManagement } from './AdminUserManagement'
import { AdminChannelManagement } from './AdminChannelManagement'
import { AdminAuditLog } from './AdminAuditLog'
import { AdminWorkspaceSettings } from './AdminWorkspaceSettings'
import { apiFetch } from '@/lib/http'

type Tab = 'overview' | 'data-sources' | 'channels' | 'ingest' | 'users' | 'audit' | 'workspace' | 'logs'

const TABS = [
  { id: 'overview'     as const, label: 'System Status'     },
  { id: 'data-sources' as const, label: 'Data Sources'      },
  { id: 'channels'     as const, label: 'Channels'          },
  { id: 'ingest'       as const, label: 'Ingest'            },
  { id: 'users'        as const, label: 'Users'             },
  { id: 'audit'        as const, label: 'Audit Log'         },
  { id: 'workspace'    as const, label: 'Workspace'         },
  { id: 'logs'         as const, label: 'System Logs'       },
]

interface DataSource {
  id:        string
  type:      'jira' | 'confluence' | 'github' | 'slack'
  name:      string
  enabled:   boolean
  last_sync: string | null
}

async function fetchSources(): Promise<{ sources: DataSource[] }> {
  const res = await apiFetch('/api/admin/data-sources')
  return res.json()
}

export function AdminDashboard() {
  const [tab, setTab] = useState<Tab>('overview')

  const { data, isError } = useQuery({
    queryKey:  ['admin-data-sources'],
    queryFn:   fetchSources,
    staleTime: 60_000,
  })

  const syncableSources = (data?.sources ?? []).filter(
    (s) => s.enabled && (s.type === 'jira' || s.type === 'confluence'),
  )

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-semibold">Admin</h1>

      <Tabs tabs={TABS} active={tab} onChange={setTab} className="mb-6" />

      <TabPanel id="overview" active={tab}>
        <div className="flex flex-col gap-6">
          <HealthCards />

          <div className="rounded-xl border border-surface-subtle p-5">
            <p className="mb-4 text-sm font-medium text-stone-500">Sync Controls</p>
            {isError ? (
              <p className="text-sm text-red-500">Failed to load data sources — check your connection and try again.</p>
            ) : syncableSources.length === 0 ? (
              <p className="text-sm text-stone-400">
                No enabled Jira or Confluence sources. Configure them in the Data Sources tab.
              </p>
            ) : (
              <div className="flex flex-col gap-3">
                {syncableSources.map((src) => (
                  <SyncTrigger
                    key={src.id}
                    source={src.type as 'jira' | 'confluence'}
                    sourceKey={src.id}
                    label={src.name}
                    lastSynced={src.last_sync ?? undefined}
                  />
                ))}
              </div>
            )}
          </div>

          <div className="rounded-xl border border-surface-subtle p-5">
            <p className="mb-4 text-sm font-medium text-stone-500">Graph Extraction</p>
            <GraphIngestButton />
          </div>
        </div>
      </TabPanel>

      <TabPanel id="data-sources" active={tab}>
        <DataSourceManager />
      </TabPanel>

      <TabPanel id="channels" active={tab}>
        <AdminChannelManagement />
      </TabPanel>

      <TabPanel id="ingest" active={tab}>
        <div className="rounded-xl border border-surface-subtle p-5">
          <p className="mb-1 text-sm font-medium text-stone-500">Upload Documents</p>
          <p className="mb-4 text-xs text-stone-400">
            Files are processed asynchronously — you can close this page after uploading.
          </p>
          <FileUploadWidget />
        </div>
      </TabPanel>

      <TabPanel id="users" active={tab}>
        <div className="rounded-xl border border-surface-subtle">
          <AdminUserManagement />
        </div>
      </TabPanel>

      <TabPanel id="audit" active={tab}>
        <AdminAuditLog />
      </TabPanel>

      <TabPanel id="workspace" active={tab}>
        <AdminWorkspaceSettings />
      </TabPanel>

      <TabPanel id="logs" active={tab}>
        <SystemLogs />
      </TabPanel>
    </div>
  )
}
