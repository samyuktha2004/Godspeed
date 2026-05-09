import { useEffect } from 'react'
import { useUIStore, type Toast } from '@/stores/uiStore'
import { cn } from '@/lib/utils'

const COLORS: Record<Toast['type'], string> = {
  info:    'bg-stone-800 text-white',
  success: 'bg-green-700 text-white',
  warning: 'bg-amber-600 text-white',
  error:   'bg-red-700 text-white',
}

function ToastItem({ toast }: { toast: Toast }) {
  const remove = useUIStore((s) => s.removeToast)

  useEffect(() => {
    const id = setTimeout(() => remove(toast.id), 5000)
    return () => clearTimeout(id)
  }, [toast.id, remove])

  return (
    <div
      role="alert"
      className={cn(
        'flex items-center justify-between gap-4 rounded-lg px-4 py-3 shadow-lg text-sm',
        COLORS[toast.type],
      )}
    >
      <span>{toast.message}</span>
      <button
        aria-label="Dismiss"
        className="opacity-70 hover:opacity-100"
        onClick={() => remove(toast.id)}
      >
        ✕
      </button>
    </div>
  )
}

export function ToastStack() {
  const toasts = useUIStore((s) => s.toasts)
  if (!toasts.length) return null
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((t) => <ToastItem key={t.id} toast={t} />)}
    </div>
  )
}
