interface Props {
  hiddenCount: number
}

export function RBACRestrictedBanner({ hiddenCount }: Props) {
  return (
    <div className="flex items-center gap-2 rounded-lg border border-stone-200 bg-stone-50 px-4 py-2 text-sm text-stone-600 dark:border-stone-700 dark:bg-stone-800/40 dark:text-stone-400">
      <span aria-hidden>🔒</span>
      <span>
        {hiddenCount} result{hiddenCount !== 1 ? 's' : ''} hidden due to your access level.
      </span>
    </div>
  )
}
