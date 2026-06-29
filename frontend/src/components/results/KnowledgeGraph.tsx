import { useEffect, useMemo, useRef, useState } from 'react'
import type { GraphNode, GraphEdge } from '@/types/api'
import { cn } from '@/lib/utils'

// ─── Colour palette ───────────────────────────────────────────────────────────

export const NODE_COLOURS: Record<GraphNode['label'], string> = {
  Service:  '#3b82f6',
  Library:  '#22c55e',
  Incident: '#ef4444',
  Team:     '#f97316',
}

// ─── Force-graph internal types ───────────────────────────────────────────────

interface FGNode {
  id:    string
  label: GraphNode['label']
  name:  string
  color: string
}

interface FGLink {
  source: string
  target: string
  rel:    string
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface Props {
  nodes:       GraphNode[]
  edges:       GraphEdge[]
  streaming:   boolean   // true while SSE/WS is active (drives the empty state animation)
  onNodeClick: (node: GraphNode) => void
  onNodeHover: (node: GraphNode | null, x: number, y: number) => void
  className?:  string
}

// ─── Component ───────────────────────────────────────────────────────────────

export function KnowledgeGraph({ nodes, edges, streaming, onNodeClick, onNodeHover, className }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const graphRef = useRef<any>(null)
  // Accumulates data that arrives before the async canvas is ready
  const pendingRef = useRef<{ nodes: GraphNode[]; edges: GraphEdge[] }>({ nodes: [], edges: [] })
  const [tableView, setTableView] = useState(false)

  const pushData = (n: GraphNode[], e: GraphEdge[]) => {
    if (!graphRef.current) return
    graphRef.current.graphData({
      nodes: n.map((node) => ({
        id:    node.id,
        label: node.label,
        name:  node.name,
        color: NODE_COLOURS[node.label] ?? '#94a3b8',
      })),
      links: e.map((edge) => ({ source: edge.from, target: edge.to, rel: edge.rel } as FGLink)),
    })
  }

  // Initialise the canvas once on mount
  useEffect(() => {
    if (!containerRef.current) return
    let ro: ResizeObserver | null = null

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    import('force-graph').then(({ default: ForceGraph2D }: any) => {
      if (!containerRef.current) return

      const el = containerRef.current

      // Track real mouse position since force-graph's onNodeHover doesn't provide it
      let mouseX = 0
      let mouseY = 0
      const trackMouse = (e: MouseEvent) => { mouseX = e.clientX; mouseY = e.clientY }
      el.addEventListener('mousemove', trackMouse)

      const fg = ForceGraph2D()
      fg(el)
      fg.backgroundColor('transparent')
        .nodeId('id')
        .nodeLabel('name')
        .nodeColor((n: FGNode) => n.color)
        .nodeRelSize(6)
        .width(el.clientWidth || 380)
        .height(el.clientHeight || 400)
        .linkColor(() => '#94a3b8')
        .linkLabel('rel')
        .linkDirectionalArrowLength(4)
        .linkDirectionalArrowRelPos(1)
        .onNodeClick((n: FGNode) => {
          onNodeClick({ id: n.id, label: n.label, name: n.name })
        })
        .onNodeHover((n: FGNode | null) => {
          onNodeHover(n ? { id: n.id, label: n.label, name: n.name } : null, mouseX, mouseY)
        })
      graphRef.current = fg

      // Auto-resize the canvas when the container is resized (e.g. maximize/collapse)
      ro = new ResizeObserver((entries) => {
        const entry = entries[0]
        if (!entry) return
        const { width, height } = entry.contentRect
        if (width > 0 && height > 0) {
          fg.width(width).height(height)
        }
      })
      ro.observe(el)

      // Flush any nodes/edges that arrived while the canvas was initialising
      pushData(pendingRef.current.nodes, pendingRef.current.edges)
    })

    return () => {
      ro?.disconnect()
      graphRef.current?._destructor?.()
      graphRef.current = null
      // trackMouse listener is on el which is removed from DOM — GC handles it
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Push updated data whenever nodes or edges change
  useEffect(() => {
    pendingRef.current = { nodes, edges }
    pushData(nodes, edges)
  }, [nodes, edges])

  const isEmpty = nodes.length === 0
  const graphLabel = isEmpty
    ? 'Knowledge graph — no data yet'
    : `Knowledge graph — ${nodes.length} node${nodes.length !== 1 ? 's' : ''}, ${edges.length} connection${edges.length !== 1 ? 's' : ''}`

  // Group edges by source and build an id→node map for O(1) table-view lookups
  const { edgesBySource, nodesById } = useMemo(() => {
    const edgesBySource: Record<string, GraphEdge[]> = {}
    const nodesById: Record<string, GraphNode> = {}
    for (const e of edges) (edgesBySource[e.from] ??= []).push(e)
    for (const n of nodes) nodesById[n.id] = n
    return { edgesBySource, nodesById }
  }, [edges, nodes])

  return (
    <div className={cn('relative h-full w-full overflow-hidden', className)}>

      {/* Accessibility toolbar — always visible, sits above canvas */}
      {!isEmpty && (
        <div className="absolute right-2 top-2 z-10">
          <button
            onClick={() => setTableView((v) => !v)}
            className="rounded border border-surface-subtle bg-white/90 px-2 py-1 text-xs text-stone-600 shadow-sm backdrop-blur-sm hover:bg-stone-50 dark:bg-stone-900/90 dark:text-stone-300 dark:hover:bg-stone-800"
            aria-pressed={tableView}
          >
            {tableView ? 'Show graph' : 'View as table'}
          </button>
        </div>
      )}

      {/* Table view — accessible alternative to the canvas */}
      {tableView && !isEmpty && (
        <div className="h-full w-full overflow-y-auto p-4">
          <table className="w-full text-sm">
            <caption className="mb-2 text-left text-xs font-semibold text-stone-500">
              {graphLabel}
            </caption>
            <thead>
              <tr className="border-b border-surface-subtle text-left text-xs text-stone-400">
                <th className="pb-2 pr-4 font-medium">Node</th>
                <th className="pb-2 pr-4 font-medium">Type</th>
                <th className="pb-2 font-medium">Connections</th>
              </tr>
            </thead>
            <tbody>
              {nodes.map((n) => (
                <tr
                  key={n.id}
                  className="cursor-pointer border-b border-surface-subtle hover:bg-stone-50 dark:hover:bg-stone-900"
                  onClick={() => onNodeClick(n)}
                >
                  <td className="py-2 pr-4 font-medium text-stone-800 dark:text-stone-200">{n.name}</td>
                  <td className="py-2 pr-4">
                    <span
                      className="inline-block h-2 w-2 rounded-full mr-1.5"
                      style={{ backgroundColor: NODE_COLOURS[n.label] ?? '#94a3b8' }}
                      aria-hidden="true"
                    />
                    {n.label}
                  </td>
                  <td className="py-2 text-stone-500">
                    {(edgesBySource[n.id] ?? []).map((e) => {
                      const target = nodesById[e.to]
                      return target ? `${e.rel} → ${target.name}` : null
                    }).filter(Boolean).join(', ') || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty state overlay — removed once first node arrives */}
      {isEmpty && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 pointer-events-none">
          {streaming ? (
            <>
              <div className="flex gap-1.5">
                <span className="h-2 w-2 animate-bounce rounded-full bg-stone-300 [animation-delay:-0.3s] dark:bg-stone-600" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-stone-300 [animation-delay:-0.15s] dark:bg-stone-600" />
                <span className="h-2 w-2 animate-bounce rounded-full bg-stone-300 dark:bg-stone-600" />
              </div>
              <p className="text-xs text-stone-400">Building knowledge graph…</p>
            </>
          ) : (
            <p className="text-sm text-stone-400">No graph data</p>
          )}
        </div>
      )}

      {/* Canvas — always present so force-graph can attach; hidden in table view */}
      <div
        ref={containerRef}
        role="img"
        aria-label={graphLabel}
        className={`h-full w-full${tableView ? ' hidden' : ''}`}
      />
    </div>
  )
}
