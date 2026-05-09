import type { RetrievedChunk } from '@/types/api'

interface Props {
  chunks: RetrievedChunk[]
}

export function RelatedDocs({ chunks }: Props) {
  if (!chunks.length) return null

  return (
    <section aria-label="Related documents">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-stone-400">
        Related
      </h2>
      <div className="grid gap-2 sm:grid-cols-2">
        {chunks.slice(0, 10).map((c) => (
          <div
            key={c.chunk_id}
            className="rounded-lg border border-surface-subtle p-3 text-sm"
          >
            <p className="truncate font-medium text-stone-800 dark:text-stone-200">{c.source}</p>
            <p className="mt-1 line-clamp-3 text-xs text-stone-500">{c.text}</p>
          </div>
        ))}
      </div>
    </section>
  )
}
