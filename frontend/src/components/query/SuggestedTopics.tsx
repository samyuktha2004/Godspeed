interface Props {
  onSelect: (query: string) => void
}

const DEFAULTS = [
  'What services does the auth team own?',
  'Show me recent incidents affecting the payments service',
  'Which libraries are deprecated in our stack?',
  'What is the onboarding process for new engineers?',
  'Summarise open Jira tickets for the infra team',
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
