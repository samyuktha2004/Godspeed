import * as Dialog from '@radix-ui/react-dialog'
import { useNotifications, type AppNotification } from '@/hooks/useNotifications'
import { cn } from '@/lib/utils'

const TYPE_ICON: Record<AppNotification['type'], string> = {
  query_answered:   '✓',
  escalation_spike: '⚠',
  breaking_change:  '🔴',
  data_sync_failed: '✕',
  knowledge_gap:    '💡',
}

interface Props {
  open:    boolean
  onClose: () => void
}

export function NotificationCenter({ open, onClose }: Props) {
  const { notifications, unreadCount, markRead, markAllRead } = useNotifications()

  return (
    <Dialog.Root open={open} onOpenChange={(o) => { if (!o) onClose() }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/20" />
        <Dialog.Content className="fixed right-4 top-16 z-50 flex w-80 flex-col overflow-hidden rounded-xl border border-surface-subtle bg-white shadow-xl dark:bg-stone-900">
          <div className="flex items-center justify-between border-b border-surface-subtle px-4 py-3">
            <Dialog.Title className="text-sm font-semibold">
              Notifications {unreadCount > 0 && <span className="ml-1 text-brand">({unreadCount})</span>}
            </Dialog.Title>
            <div className="flex items-center gap-2">
              {unreadCount > 0 && (
                <button onClick={markAllRead} className="text-xs text-stone-400 hover:text-stone-600">
                  Mark all read
                </button>
              )}
              <Dialog.Close className="text-stone-400 hover:text-stone-600" aria-label="Close">✕</Dialog.Close>
            </div>
          </div>

          <div className="max-h-[480px] overflow-y-auto">
            {notifications.length === 0 && (
              <p className="px-4 py-8 text-center text-sm text-stone-400">No notifications yet</p>
            )}
            {notifications.map((n) => (
              <button
                key={n.id}
                onClick={() => markRead(n.id)}
                className={cn(
                  'flex w-full items-start gap-3 px-4 py-3 text-left text-sm transition-colors hover:bg-stone-50 dark:hover:bg-stone-800',
                  !n.read && 'bg-brand/5',
                )}
              >
                <span className="mt-0.5 shrink-0 text-base" aria-hidden>
                  {TYPE_ICON[n.type]}
                </span>
                <div className="min-w-0 flex-1">
                  <p className={cn('text-stone-700 dark:text-stone-300', !n.read && 'font-medium')}>
                    {n.message}
                  </p>
                  <p className="mt-0.5 text-xs text-stone-400">{n.timestamp}</p>
                </div>
                {!n.read && (
                  <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-brand" aria-hidden />
                )}
              </button>
            ))}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}
