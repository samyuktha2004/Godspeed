import { cn } from '@/lib/utils'
import type { AgentTask } from '@/types/api'

type AgentState = 'pending' | 'active' | 'done'

export interface AgentStatus {
  agent: string
  state: AgentState
  confidence?: 'high' | 'medium' | 'low'
}

interface Props {
  plan: AgentTask[]
  statuses: Record<string, AgentStatus>
}

const CONFIDENCE_COLOUR: Record<string, string> = {
  high:   'text-green-600 dark:text-green-400',
  medium: 'text-amber-500 dark:text-amber-400',
  low:    'text-red-500 dark:text-red-400',
}

export function AgentBadges({ plan, statuses }: Props) {
  if (!plan.length) return null

  return (
    <div className="flex flex-wrap gap-2" role="status" aria-label="Agent execution status">
      {plan.map(({ agent }) => {
        const s = statuses[agent] ?? { agent, state: 'pending' }
        return (
          <span
            key={agent}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium',
              s.state === 'pending' && 'border-stone-200 text-stone-400 dark:border-stone-700 dark:text-stone-500',
              s.state === 'active'  && 'border-brand/50 bg-brand/10 text-brand animate-pulse',
              s.state === 'done'    && 'border-green-200 bg-green-50 text-green-700 dark:border-green-800 dark:bg-green-950/30 dark:text-green-400',
            )}
          >
            {s.state === 'done'   && <span aria-hidden>✓</span>}
            {s.state === 'active' && <span aria-hidden>●</span>}
            {agent.replace('_', ' ')}
            {s.state === 'done' && s.confidence && (
              <span className={cn('ml-1', CONFIDENCE_COLOUR[s.confidence])}>
                {s.confidence}
              </span>
            )}
          </span>
        )
      })}
    </div>
  )
}
