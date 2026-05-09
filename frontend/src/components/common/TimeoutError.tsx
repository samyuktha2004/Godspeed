interface Props {
  message?: string
  onRetry?: () => void
}

export function TimeoutError({ message, onRetry }: Props) {
  return (
    <div className="flex flex-col items-center gap-4 py-16 text-center">
      <p className="text-2xl">⏱</p>
      <p className="text-base font-medium text-stone-700 dark:text-stone-300">
        {message ?? 'The query took too long to respond.'}
      </p>
      <p className="text-sm text-stone-500 dark:text-stone-400">
        This can happen when agents are under heavy load. Try again in a moment.
      </p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-2 rounded bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark"
        >
          Retry
        </button>
      )}
    </div>
  )
}
