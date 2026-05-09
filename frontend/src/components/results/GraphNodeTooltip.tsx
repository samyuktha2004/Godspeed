import { useEffect, useRef } from 'react'
import type { GraphNode } from '@/types/api'
import { NODE_COLOURS } from './KnowledgeGraph'

interface Props {
  node: GraphNode | null
  x:    number
  y:    number
}

export function GraphNodeTooltip({ node, x, y }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  // Clamp position so tooltip never overflows viewport
  useEffect(() => {
    if (!ref.current || !node) return
    const el     = ref.current
    const margin = 12
    let left = x + margin
    let top  = y + margin

    const { width, height } = el.getBoundingClientRect()
    if (left + width  > window.innerWidth  - margin) left = x - width  - margin
    if (top  + height > window.innerHeight - margin) top  = y - height - margin

    el.style.left = `${left}px`
    el.style.top  = `${top}px`
  }, [node, x, y])

  if (!node) return null

  const colour = NODE_COLOURS[node.label] ?? '#94a3b8'

  return (
    <div
      ref={ref}
      className="pointer-events-none fixed z-50 rounded-lg border border-surface-subtle bg-white px-3 py-2 shadow-md dark:bg-stone-900"
      style={{ left: x + 12, top: y + 12 }}
      role="tooltip"
    >
      <p className="text-sm font-semibold text-stone-800 dark:text-stone-100">{node.name}</p>
      <span
        className="mt-0.5 inline-block rounded px-1.5 py-0.5 text-xs font-medium text-white"
        style={{ backgroundColor: colour }}
      >
        {node.label}
      </span>
    </div>
  )
}
