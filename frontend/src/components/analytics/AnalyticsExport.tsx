import { useState } from 'react'
import { apiFetch } from '@/lib/http'
import { cn } from '@/lib/utils'

type ExportFormat = 'csv' | 'pdf'
type ExportScope  = 'queries' | 'topics' | 'health' | 'escalations' | 'full'

const SCOPES: Array<{ id: ExportScope; label: string; desc: string }> = [
  { id: 'queries',     label: 'Query analytics',      desc: 'Volume, success rate, response times' },
  { id: 'topics',      label: 'Top topics',           desc: 'Most-queried subjects'                },
  { id: 'health',      label: 'Knowledge health',     desc: 'Coverage, freshness, accuracy scores' },
  { id: 'escalations', label: 'Escalations',          desc: 'Unresolved queries by frequency'      },
  { id: 'full',        label: 'Full report',          desc: 'All of the above combined'            },
]

export function AnalyticsExport({ teamId }: { teamId?: string | null }) {
  const [scope,      setScope]      = useState<ExportScope>('full')
  const [format,     setFormat]     = useState<ExportFormat>('csv')
  const [dateRange,  setDateRange]  = useState('30d')
  const [exporting,  setExporting]  = useState(false)

  async function handleExport() {
    setExporting(true)
    try {
      const params = new URLSearchParams({ scope, format, date_range: dateRange })
      if (teamId) params.set('team_id', teamId)
      const res = await apiFetch(`/api/analytics/export?${params}`)
      const blob        = await res.blob()
      const ext         = format === 'pdf' ? 'pdf' : 'csv'
      const filename    = `godspeed-analytics-${scope}-${dateRange}.${ext}`
      const url         = URL.createObjectURL(blob)
      const a           = document.createElement('a')
      a.href            = url
      a.download        = filename
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="rounded-xl border border-surface-subtle p-5">
      <p className="mb-4 text-sm font-medium text-stone-500">Export Analytics</p>

      <div className="flex flex-col gap-5 sm:flex-row sm:items-end">
        {/* Scope */}
        <div className="flex-1">
          <label className="mb-1.5 block text-xs font-medium text-stone-500">Report scope</label>
          <div className="flex flex-col gap-1.5">
            {SCOPES.map((s) => (
              <label
                key={s.id}
                className={cn(
                  'flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors',
                  scope === s.id
                    ? 'border-brand bg-amber-50 dark:bg-amber-950/20'
                    : 'border-surface-subtle hover:border-stone-300',
                )}
              >
                <input
                  type="radio"
                  name="scope"
                  value={s.id}
                  checked={scope === s.id}
                  onChange={() => setScope(s.id)}
                  className="mt-0.5 accent-amber-700"
                />
                <div>
                  <p className="text-sm font-medium">{s.label}</p>
                  <p className="text-xs text-stone-400">{s.desc}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Format + date range + button */}
        <div className="flex flex-col gap-4 sm:w-48">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-stone-500">Format</label>
            <div className="flex rounded-lg border border-surface-subtle text-sm">
              {(['csv', 'pdf'] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFormat(f)}
                  className={cn(
                    'flex-1 py-2 transition-colors first:rounded-l-lg last:rounded-r-lg font-medium uppercase tracking-wide',
                    format === f
                      ? 'bg-brand text-white'
                      : 'text-stone-500 hover:text-stone-700',
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-stone-500">Date range</label>
            <select
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value)}
              className="w-full rounded-lg border border-surface-subtle bg-white px-3 py-2 text-sm dark:bg-stone-900"
            >
              <option value="7d">Last 7 days</option>
              <option value="30d">Last 30 days</option>
              <option value="90d">Last 90 days</option>
              <option value="all">All time</option>
            </select>
          </div>

          <button
            onClick={handleExport}
            disabled={exporting}
            className={cn(
              'flex items-center justify-center gap-2 rounded-lg py-2.5 text-sm font-semibold transition-colors',
              exporting
                ? 'cursor-not-allowed bg-stone-200 text-stone-400 dark:bg-stone-700'
                : 'bg-brand text-white hover:bg-brand/90',
            )}
          >
            {exporting ? (
              <>
                <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Exporting…
              </>
            ) : (
              <>
                <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clipRule="evenodd" />
                </svg>
                Download {format.toUpperCase()}
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
