import { useState } from 'react'
import { apiFetch, ApiError } from '@/lib/http'
import { useUIStore } from '@/stores/uiStore'
import { cn } from '@/lib/utils'

interface Props {
  queryId: string
}

type Sentiment = 'helpful' | 'not_helpful' | 'hallucinated'

export function QueryFeedback({ queryId }: Props) {
  const [sent, setSent]           = useState<Sentiment | null>(null)
  const [showFlag, setShowFlag]   = useState(false)
  const [text, setText]           = useState('')
  const [submitting, setSubmitting] = useState(false)
  const addToast = useUIStore((s) => s.addToast)

  const submit = async (sentiment: Sentiment, extraText?: string) => {
    setSubmitting(true)
    try {
      await apiFetch(`/api/query/${queryId}/feedback`, {
        method: 'POST',
        body:   JSON.stringify({ sentiment, text: (extraText ?? text) || undefined }),
      })
      setSent(sentiment)
      setShowFlag(false)
      addToast({ type: 'success', message: 'Feedback recorded — thank you' })
    } catch (err) {
      if (!(err instanceof ApiError)) {
        addToast({ type: 'error', message: 'Could not submit feedback' })
      }
    } finally {
      setSubmitting(false)
    }
  }

  if (sent) {
    return (
      <p className="text-xs text-stone-400">
        {sent === 'helpful' ? '👍 Marked as helpful' : '👎 Feedback recorded'}
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <span className="text-xs text-stone-400">Was this answer useful?</span>
        <button
          onClick={() => submit('helpful')}
          disabled={submitting}
          className={cn('rounded-lg border px-3 py-1 text-xs transition-colors hover:border-green-400 hover:text-green-600', submitting && 'opacity-50')}
          aria-label="Mark as helpful"
        >
          👍
        </button>
        <button
          onClick={() => setShowFlag(true)}
          disabled={submitting}
          className={cn('rounded-lg border px-3 py-1 text-xs transition-colors hover:border-red-400 hover:text-red-600', submitting && 'opacity-50')}
          aria-label="Mark as not helpful"
        >
          👎
        </button>
      </div>

      {showFlag && (
        <div className="flex flex-col gap-2 rounded-lg border border-surface-subtle p-3">
          <p className="text-xs font-medium text-stone-600 dark:text-stone-400">What was wrong?</p>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Optional — describe the issue"
            rows={2}
            className="w-full resize-none rounded border border-surface-subtle px-3 py-2 text-xs outline-none focus:border-brand dark:bg-stone-800"
          />
          <div className="flex gap-2">
            <button
              onClick={() => submit('not_helpful')}
              disabled={submitting}
              className="rounded bg-stone-100 px-3 py-1.5 text-xs text-stone-700 hover:bg-stone-200 disabled:opacity-50 dark:bg-stone-800 dark:text-stone-300"
            >
              Not helpful
            </button>
            <button
              onClick={() => submit('hallucinated')}
              disabled={submitting}
              className="rounded bg-red-50 px-3 py-1.5 text-xs text-red-700 hover:bg-red-100 disabled:opacity-50 dark:bg-red-950/30 dark:text-red-400"
            >
              Flag as hallucination
            </button>
            <button
              onClick={() => setShowFlag(false)}
              className="ml-auto text-xs text-stone-400 hover:text-stone-600"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
