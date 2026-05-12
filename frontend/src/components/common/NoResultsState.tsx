interface Props {
  query: string
}

const SUGGESTIONS = [
  'Try broader terms — remove acronyms or product names',
  'Results may be limited based on your channel access — ask your admin if you need broader access',
  'Check if the data source containing this topic is connected',
  'Ask your admin to verify ingestion status for that area',
]

export function NoResultsState({ query }: Props) {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <p className="text-2xl">🔍</p>
      <p className="text-base font-medium text-stone-700 dark:text-stone-300">
        No results for <span className="italic">"{query}"</span>
      </p>
      <ul className="mt-1 space-y-1 text-sm text-stone-500 dark:text-stone-400">
        {SUGGESTIONS.map((s) => (
          <li key={s}>• {s}</li>
        ))}
      </ul>
    </div>
  )
}
