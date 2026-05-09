import { useCallback, useEffect, useRef, useState } from 'react'
import { env } from '@/config/env'
import { useUIStore } from '@/stores/uiStore'

export interface AppNotification {
  id:        string
  type:      'query_answered' | 'escalation_spike' | 'breaking_change' | 'data_sync_failed' | 'knowledge_gap'
  message:   string
  timestamp: string
  read:      boolean
}

export function useNotifications() {
  const [notifications, setNotifications] = useState<AppNotification[]>([])
  const wsRef   = useRef<WebSocket | null>(null)
  const addToast = useUIStore.getState().addToast

  const connect = useCallback(() => {
    const ws = new WebSocket(`${env.wsBaseUrl}/ws`)
    wsRef.current = ws

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data as string) as Omit<AppNotification, 'id' | 'read'>
        const notification: AppNotification = {
          ...msg,
          id:   crypto.randomUUID(),
          read: false,
        }
        setNotifications((prev) => [notification, ...prev].slice(0, 50))
        addToast({ type: 'info', message: notification.message })
      } catch {
        // Non-JSON or unknown frame — ignore
      }
    }

    // Gracefully no-op if endpoint is 404 or unavailable — notifications are non-critical
    ws.onerror  = () => {}
    ws.onclose  = () => {}
  }, [addToast])

  const markRead = useCallback((id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n)),
    )
  }, [])

  const markAllRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
  }, [])

  const unreadCount = notifications.filter((n) => !n.read).length

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [connect])

  return { notifications, unreadCount, markRead, markAllRead }
}
