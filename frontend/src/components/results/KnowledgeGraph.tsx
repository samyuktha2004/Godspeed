import { useEffect, useRef } from 'react'
import type { GraphNode, GraphEdge } from '@/types/api'
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton'

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
  nodes:            GraphNode[]
  edges:            GraphEdge[]
  loading:          boolean   // true while SSE streaming but no nodes yet
  onNodeClick:      (node: GraphNode) => void
  onNodeHover:      (node: GraphNode | null, x: number, y: number) => void
}

// ─── Component ───────────────────────────────────────────────────────────────

export function KnowledgeGraph({ nodes, edges, loading, onNodeClick, onNodeHover }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const graphRef = useRef<any>(null)
  // Keep latest nodes/edges in a ref so the async init callback can read them
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
      links: e.map((edge) => ({ source: edge.from, target: edge.to, rel: edge.rel })),
    })
  }

  // Initialise the canvas once on mount
  useEffect(() => {
    if (!containerRef.current) return

    import('force-graph').then(({ default: ForceGraph2D }) => {
      if (!containerRef.current) return

      // ForceGraph2D() returns a component function; call it with the element to mount
      const fg = ForceGraph2D()
      fg(containerRef.current)
      fg.backgroundColor('transparent')
        .nodeId('id')
        .nodeLabel('name')
        .nodeColor((n: FGNode) => n.color)
        .nodeRelSize(6)
        .width(containerRef.current.clientWidth || 380)
        .height(containerRef.current.clientHeight || 400)
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

      // Push any data that arrived before the canvas was ready
      pushData(pendingRef.current.nodes, pendingRef.current.edges)
    })

    return () => {
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

  return (
    <div className="relative hidden h-[400px] w-full overflow-hidden rounded-xl border border-surface-subtle lg:block">
      {loading && nodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center">
          <LoadingSkeleton rows={2} className="w-3/4" />
        </div>
      )}
      {!loading && nodes.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-stone-400">
          No graph data yet
        </div>
      )}
      <div ref={containerRef} className="h-full w-full" aria-label="Knowledge graph visualisation" />
    </div>
  )
}
