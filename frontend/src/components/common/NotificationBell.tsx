import { useState } from 'react'
import { useNotifications } from '@/hooks/useNotifications'
import { NotificationCenter } from './NotificationCenter'

export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const { unreadCount } = useNotifications()

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="relative rounded-lg p-2 text-stone-500 hover:bg-stone-100 hover:text-stone-700 dark:hover:bg-stone-800 dark:hover:text-stone-200"
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
      >
        <span className="text-lg" aria-hidden>🔔</span>
        {unreadCount > 0 && (
          <span className="absolute right-1 top-1 flex h-4 w-4 items-center justify-center rounded-full bg-brand text-[10px] font-bold text-white">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      <NotificationCenter open={open} onClose={() => setOpen(false)} />
    </>
  )
}
