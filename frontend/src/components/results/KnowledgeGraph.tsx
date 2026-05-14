import { useEffect, useRef } from 'react'
import type { GraphNode, GraphEdge } from '@/types/api'

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
          onNodeHover(n ? { id: n.id, label: n.label, name: n.name } : null, 0, 0)
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
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Push updated data whenever nodes or edges change
  useEffect(() => {
    pendingRef.current = { nodes, edges }
    pushData(nodes, edges)
  }, [nodes, edges])

  const isEmpty = nodes.length === 0

  return (
    <div className={`relative h-full w-full overflow-hidden${className ? ` ${className}` : ''}`}>

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

      {/* Canvas — always present so force-graph can attach */}
      <div
        ref={containerRef}
        className="h-full w-full"
        aria-label="Knowledge graph visualisation"
      />
    </div>
  )
}
