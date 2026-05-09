interface Props {
  attempt: number
  maxAttempts?: number
}

export function NetworkRetry({ attempt, maxAttempts = 5 }: Props) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-stone-200 bg-stone-50 px-4 py-3 text-sm dark:border-stone-700 dark:bg-stone-800/40">
      <span className="animate-spin text-base" aria-hidden>⟳</span>
      <span className="text-stone-600 dark:text-stone-400">
        Graph stream disconnected — reconnecting (attempt {attempt}/{maxAttempts})…
      </span>
    </div>
  )
}
