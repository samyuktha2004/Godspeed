import { useState } from 'react'
import { HealthCards } from './HealthCards'
import { SyncTrigger } from './SyncTrigger'
import { GraphIngestButton } from './GraphIngestButton'
import { FileUploadWidget } from './FileUploadWidget'
import { DataSourceManager } from './DataSourceManager'
import { SystemLogs } from './SystemLogs'
import { AdminUserManagement } from './AdminUserManagement'

type Tab = 'overview' | 'data-sources' | 'ingest' | 'users' | 'logs'

const TABS: { id: Tab; label: string }[] = [
  { id: 'overview',      label: 'System Status' },
  { id: 'data-sources',  label: 'Data Sources'  },
  { id: 'ingest',        label: 'Ingest'         },
  { id: 'users',         label: 'Users'          },
  { id: 'logs',          label: 'System Logs'    },
]

export function AdminDashboard() {
  const [tab, setTab] = useState<Tab>('overview')

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <h1 className="mb-6 text-2xl font-semibold">Admin</h1>

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
          <HealthCards />

          <div className="rounded-xl border border-surface-subtle p-5">
            <p className="mb-4 text-sm font-medium text-stone-500">Sync Controls</p>
            <div className="flex flex-col gap-3">
              <SyncTrigger source="jira"       sourceKey="KAN"      label="Jira (KAN)"           />
              <SyncTrigger source="confluence" sourceKey="Godspeed" label="Confluence (Godspeed)" />
            </div>
          </div>

          <div className="rounded-xl border border-surface-subtle p-5">
            <p className="mb-4 text-sm font-medium text-stone-500">Graph Extraction</p>
            <GraphIngestButton />
          </div>
        </div>
      )}

      {tab === 'data-sources' && <DataSourceManager />}

      {tab === 'ingest' && (
        <div className="rounded-xl border border-surface-subtle p-5">
          <p className="mb-4 text-sm font-medium text-stone-500">Upload Documents</p>
          <p className="mb-4 text-xs text-stone-400">
            Files are processed asynchronously — you can close this page after uploading.
          </p>
          <FileUploadWidget />
        </div>
      )}

      {tab === 'users' && (
        <div className="rounded-xl border border-surface-subtle">
          <AdminUserManagement />
        </div>
      )}

      {tab === 'logs' && <SystemLogs />}
    </div>
  )
}
