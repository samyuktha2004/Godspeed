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
  // Store the ForceGraph2D instance — typed as any because force-graph has no bundled types
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const graphRef = useRef<any>(null)

  // Initialise the canvas once on mount
  useEffect(() => {
    if (!containerRef.current) return

    // Dynamic import — force-graph is a large canvas lib; keep it out of initial bundle
    import('force-graph').then(({ default: ForceGraph2D }) => {
      if (!containerRef.current) return

      graphRef.current = ForceGraph2D(containerRef.current)
        .backgroundColor('transparent')
        .nodeId('id')
        .nodeLabel('name')
        .nodeColor((n: FGNode) => n.color)
        .nodeRelSize(6)
        .linkColor(() => '#94a3b8')
        .linkLabel('rel')
        .linkDirectionalArrowLength(4)
        .linkDirectionalArrowRelPos(1)
        .onNodeClick((n: FGNode) => {
          onNodeClick({ id: n.id, label: n.label, name: n.name })
        })
        .onNodeHover((n: FGNode | null, _prev: unknown, event: MouseEvent) => {
          const x = event?.clientX ?? 0
          const y = event?.clientY ?? 0
          onNodeHover(n ? { id: n.id, label: n.label, name: n.name } : null, x, y)
        })
    })

    return () => {
      // force-graph cleanup
      graphRef.current?._destructor?.()
      graphRef.current = null
    }
    // onNodeClick / onNodeHover are stable callbacks passed from parent via useCallback
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Push updated data whenever nodes or edges change
  useEffect(() => {
    if (!graphRef.current) return

    const fgNodes: FGNode[] = nodes.map((n) => ({
      id:    n.id,
      label: n.label,
      name:  n.name,
      color: NODE_COLOURS[n.label] ?? '#94a3b8',
    }))

    const fgLinks: FGLink[] = edges.map((e) => ({
      source: e.from,
      target: e.to,
      rel:    e.rel,
    }))

    graphRef.current.graphData({ nodes: fgNodes, links: fgLinks })
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
