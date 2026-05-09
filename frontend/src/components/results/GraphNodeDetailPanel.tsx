import * as Dialog from '@radix-ui/react-dialog'
import { useQuery } from '@tanstack/react-query'
import { apiFetch } from '@/lib/http'
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton'
import { NODE_COLOURS } from './KnowledgeGraph'
import type { GraphNode, GraphTraverseResponse } from '@/types/api'

interface Props {
  node:        GraphNode | null
  teamId:      string
  onClose:     () => void
  onAskAbout:  (query: string) => void
}

async function fetchTraverse(node: GraphNode, teamId: string): Promise<GraphTraverseResponse> {
  const params = new URLSearchParams({
    type:    node.label.toLowerCase(),
    name:    node.name,
    team_id: teamId,
  })
  const res = await apiFetch(`/graph/traverse?${params}`)
  return res.json()
}

export function GraphNodeDetailPanel({ node, teamId, onClose, onAskAbout }: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey:  ['graph-traverse', node?.label, node?.name, teamId],
    queryFn:   () => fetchTraverse(node!, teamId),
    enabled:   !!node,
    staleTime: 60_000,
    retry:     1,
  })

  const colour = node ? (NODE_COLOURS[node.label] ?? '#94a3b8') : '#94a3b8'

  return (
    <Dialog.Root open={!!node} onOpenChange={(open) => { if (!open) onClose() }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm" />
        <Dialog.Content
          className="fixed right-0 top-0 z-50 flex h-full w-full max-w-sm flex-col border-l border-surface-subtle bg-white shadow-xl dark:bg-stone-900"
          aria-describedby="panel-desc"
        >
          {node && (
            <>
              {/* Header */}
              <div className="flex items-start justify-between border-b border-surface-subtle p-5">
                <div>
                  <Dialog.Title className="text-base font-semibold text-stone-900 dark:text-stone-100">
                    {node.name}
                  </Dialog.Title>
                  <span
                    className="mt-1 inline-block rounded px-2 py-0.5 text-xs font-medium text-white"
                    style={{ backgroundColor: colour }}
                  >
                    {node.label}
                  </span>
                </div>
                <Dialog.Close asChild>
                  <button
                    className="rounded p-1 text-stone-400 hover:text-stone-700 dark:hover:text-stone-200"
                    aria-label="Close panel"
                  >
                    ✕
                  </button>
                </Dialog.Close>
              </div>

              {/* Body */}
              <div id="panel-desc" className="flex-1 overflow-y-auto p-5">
                <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-stone-400">
                  Related documents
                </p>

                {isLoading && <LoadingSkeleton rows={3} />}

                {isError && (
                  <p className="text-sm text-stone-500">Could not load related documents.</p>
                )}

                {data && data.chunks.length === 0 && (
                  <p className="text-sm text-stone-500">No related documents found.</p>
                )}

                {data && data.chunks.length > 0 && (
                  <div className="flex flex-col gap-3">
                    {data.chunks.slice(0, 6).map((chunk, i) => (
                      <div
                        key={i}
                        className="rounded-lg border border-surface-subtle p-3 text-sm text-stone-700 dark:text-stone-300"
                      >
                        {chunk.length > 200 ? chunk.slice(0, 200) + '…' : chunk}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="border-t border-surface-subtle p-4">
                <button
                  onClick={() => {
                    onClose()
                    onAskAbout(`Tell me about ${node.name}`)
                  }}
                  className="w-full rounded-lg bg-brand py-2.5 text-sm font-medium text-white hover:bg-brand-dark"
                >
                  Ask about {node.name}
                </button>
              </div>
            </>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
