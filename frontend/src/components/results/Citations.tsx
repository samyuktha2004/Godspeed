import type { RetrievedChunk } from '@/types/api'

interface Props {
  chunks: RetrievedChunk[]
}

const SOURCE_BADGE: Record<string, string> = {
  jira:       'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  confluence: 'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400',
  file:       'bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-400',
  url:        'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
}

function sourceLabel(sourceType: string) {
  return sourceType.charAt(0).toUpperCase() + sourceType.slice(1)
}

export function Citations({ chunks }: Props) {
  if (!chunks.length) return null

  return (
    <section aria-label="Sources">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-stone-400">
        Sources
      </h2>
      <div className="flex flex-col gap-2">
        {chunks.map((c) => (
          <div
            key={c.chunk_id}
            className="flex items-start gap-3 rounded-lg border border-surface-subtle p-3 text-sm"
          >
            <span
              className={`shrink-0 rounded px-2 py-0.5 text-xs font-medium ${SOURCE_BADGE[c.source_type] ?? SOURCE_BADGE.file}`}
            >
              {sourceLabel(c.source_type)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-stone-800 dark:text-stone-200">{c.source}</p>
              <p className="mt-0.5 line-clamp-2 text-stone-500">{c.text}</p>
            </div>
            {c.source.startsWith('http') && (
              <a
                href={c.source}
                target="_blank"
                rel="noopener noreferrer"
                className="shrink-0 text-xs text-brand hover:underline"
                aria-label="Open source"
              >
                ↗
              </a>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}
