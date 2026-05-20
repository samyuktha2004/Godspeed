interface Props {
  onSelect: (query: string) => void
}

const DEFAULTS = [
  'What is Godspeed and what does it do?',
  'How do I set up Godspeed locally?',
  'What are the main components of the Godspeed architecture?',
  'What API endpoints does Godspeed expose?',
  'What is the incident runbook for Godspeed?',
]

export function SuggestedTopics({ onSelect }: Props) {
  return (
    <div className="flex flex-wrap justify-center gap-2">
      {DEFAULTS.map((q) => (
        <button
          key={q}
          onClick={() => onSelect(q)}
          className="rounded-full border border-surface-subtle px-3 py-1.5 text-xs text-stone-600 hover:border-brand hover:text-brand dark:text-stone-400 dark:hover:text-brand"
        >
          {q}
        </button>
      ))}
    </div>
  )
}
