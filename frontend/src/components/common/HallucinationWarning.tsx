interface Props {
  onReport?: () => void
}

export function HallucinationWarning({ onReport }: Props) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 dark:border-amber-800 dark:bg-amber-950/30">
      <span className="mt-0.5 text-amber-500" aria-hidden>⚠</span>
      <div className="flex-1 text-sm text-amber-800 dark:text-amber-200">
        This answer may not be fully accurate. Verify against the cited sources before acting on it.
      </div>
      {onReport && (
        <button
          onClick={onReport}
          className="shrink-0 text-xs text-amber-600 underline hover:text-amber-800 dark:text-amber-400"
        >
          Report
        </button>
      )}
    </div>
  )
}
