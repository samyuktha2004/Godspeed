import { useEffect, useRef } from 'react'
import { cn } from '@/lib/utils'

interface Props {
  onSubmit:     (query: string) => void
  disabled?:    boolean
  className?:   string
  defaultValue?: string
}

export function SearchBox({ onSubmit, disabled, className, defaultValue }: Props) {
  const ref = useRef<HTMLInputElement>(null)

  // Cmd+K / Ctrl+K → focus from anywhere
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        ref.current?.focus()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  const submit = () => {
    const value = ref.current?.value.trim()
    if (value) {
      onSubmit(value)
      if (ref.current) ref.current.value = ''
    }
  }

  return (
    <div className={cn('flex w-full items-center gap-2 rounded-xl border border-surface-subtle bg-white px-4 py-3 shadow-sm focus-within:border-brand dark:bg-stone-900', className)}>
      <span className="text-stone-400" aria-hidden>⌕</span>
      <input
        ref={ref}
        type="text"
        defaultValue={defaultValue}
        placeholder="Ask anything… (⌘K)"
        disabled={disabled}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
        className="flex-1 bg-transparent text-sm outline-none placeholder:text-stone-400 disabled:opacity-60"
        aria-label="Query input"
      />
      <button
        onClick={submit}
        disabled={disabled}
        className="rounded-lg bg-brand px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-dark disabled:opacity-60"
      >
        Ask
      </button>
    </div>
  )
}
