import { cn } from '@/lib/utils'

interface Props {
  className?: string
  /** How many stacked rows to show. Default 3. */
  rows?: number
}

/**
 * Single pulsing placeholder.
 * Rule: render only when zero SSE events AND zero graph nodes have arrived.
 * Disappears the moment any data lands — never re-shown for that query session.
 */
export function LoadingSkeleton({ className, rows = 3 }: Props) {
  return (
    <div
      className={cn('flex flex-col gap-3 p-6', className)}
      role="status"
      aria-label="Loading…"
    >
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className={cn(
            'skeleton h-4',
            i === 0 && 'w-3/4',
            i === 1 && 'w-full',
            i === 2 && 'w-1/2',
          )}
        />
      ))}
    </div>
  )
}
