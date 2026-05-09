import { useRef } from 'react'

interface Props {
  onSubmit: (query: string) => void
  disabled?: boolean
}

export function FollowUp({ onSubmit, disabled }: Props) {
  const ref = useRef<HTMLInputElement>(null)

  const submit = () => {
    const value = ref.current?.value.trim()
    if (value) {
      onSubmit(value)
      if (ref.current) ref.current.value = ''
    }
  }

  return (
    <div className="flex items-center gap-2 rounded-xl border border-surface-subtle bg-white px-4 py-3 shadow-sm focus-within:border-brand dark:bg-stone-900">
      <input
        ref={ref}
        type="text"
        placeholder="Ask a follow-up…"
        disabled={disabled}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
        className="flex-1 bg-transparent text-sm outline-none placeholder:text-stone-400 disabled:opacity-60"
        aria-label="Follow-up query"
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
