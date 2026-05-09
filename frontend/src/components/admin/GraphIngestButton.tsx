import { useState } from 'react'
import { apiFetch, ApiError } from '@/lib/http'
import { useUIStore } from '@/stores/uiStore'

interface Props {
  /** Specific chunk IDs to process. When omitted, all pending chunks are processed. */
  chunkIds?: string[]
  teamId?:   string
}

export function GraphIngestButton({ chunkIds, teamId = 'default' }: Props) {
  const [loading, setLoading] = useState(false)
  const addToast              = useUIStore((s) => s.addToast)

  const run = async () => {
    setLoading(true)
    try {
      const body: Record<string, unknown> = { team_id: teamId }
      if (chunkIds) body.chunk_ids = chunkIds

      const res  = await apiFetch('/graph/ingest', {
        method: 'POST',
        body:   JSON.stringify(body),
      })
      const data = await res.json() as { ingested: number }
      addToast({
        type:    'success',
        message: `Ingested ${data.ingested} entit${data.ingested === 1 ? 'y' : 'ies'} into knowledge graph`,
      })
    } catch (err) {
      if (!(err instanceof ApiError)) {
        addToast({ type: 'error', message: 'Graph extraction failed' })
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <button
      onClick={run}
      disabled={loading}
      className="flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-60"
    >
      {loading && <span className="animate-spin" aria-hidden>⟳</span>}
      {loading ? 'Extracting entities…' : 'Run graph extraction'}
    </button>
  )
}
