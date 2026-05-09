import * as Dialog from '@radix-ui/react-dialog'
import { useState } from 'react'
import { useUIStore } from '@/stores/uiStore'

interface Props {
  query:   string
  open:    boolean
  onClose: () => void
}

export function ShareResults({ query, open, onClose }: Props) {
  const [copied, setCopied] = useState(false)
  const addToast = useUIStore((s) => s.addToast)

  const shareUrl = `${window.location.origin}/query?q=${encodeURIComponent(query)}`

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
      addToast({ type: 'success', message: 'Link copied to clipboard' })
    } catch {
      addToast({ type: 'error', message: 'Could not copy to clipboard' })
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-full max-w-md -translate-x-1/2 -translate-y-1/2 rounded-xl border border-surface-subtle bg-white p-6 shadow-xl dark:bg-stone-900">
          <div className="mb-4 flex items-center justify-between">
            <Dialog.Title className="text-base font-semibold">Share this answer</Dialog.Title>
            <Dialog.Close className="text-stone-400 hover:text-stone-600" aria-label="Close">✕</Dialog.Close>
          </div>

          <p className="mb-3 text-sm text-stone-500">
            Anyone with this link can view the query — results are re-run live with their own access level.
          </p>

          <div className="flex items-center gap-2 rounded-lg border border-surface-subtle bg-stone-50 px-3 py-2 dark:bg-stone-800">
            <span className="flex-1 truncate font-mono text-xs text-stone-600 dark:text-stone-400">
              {shareUrl}
            </span>
            <button
              onClick={copy}
              className="shrink-0 rounded bg-brand px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-dark"
            >
              {copied ? 'Copied!' : 'Copy'}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
