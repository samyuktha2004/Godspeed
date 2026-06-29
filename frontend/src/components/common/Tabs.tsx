import { cn } from '@/lib/utils'

export interface TabItem<T extends string = string> {
  id:    T
  label: string
}

interface Props<T extends string> {
  tabs:     TabItem<T>[]
  active:   T
  onChange: (id: T) => void
  className?: string
}

export function Tabs<T extends string>({ tabs, active, onChange, className }: Props<T>) {
  return (
    <div
      role="tablist"
      aria-orientation="horizontal"
      className={cn('flex gap-1 overflow-x-auto border-b border-surface-subtle', className)}
    >
      {tabs.map((t) => {
        const isActive = t.id === active
        return (
          <button
            key={t.id}
            role="tab"
            aria-selected={isActive}
            aria-controls={`tabpanel-${t.id}`}
            id={`tab-${t.id}`}
            onClick={() => onChange(t.id)}
            className={cn(
              'whitespace-nowrap px-4 py-2 text-sm font-medium transition-colors',
              isActive
                ? 'border-b-2 border-brand text-brand'
                : 'text-stone-500 hover:text-stone-700 dark:hover:text-stone-300',
            )}
          >
            {t.label}
          </button>
        )
      })}
    </div>
  )
}

interface PanelProps {
  id:       string
  active:   string
  children: React.ReactNode
  className?: string
}

export function TabPanel({ id, active, children, className }: PanelProps) {
  if (id !== active) return null
  return (
    <div
      role="tabpanel"
      id={`tabpanel-${id}`}
      aria-labelledby={`tab-${id}`}
      className={className}
    >
      {children}
    </div>
  )
}
