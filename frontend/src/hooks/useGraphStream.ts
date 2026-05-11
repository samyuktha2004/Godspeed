import { useCallback, useEffect, useRef, useState } from 'react'
import { env } from '@/config/env'
import type { GraphNode, GraphEdge, GraphDoneEvent } from '@/types/api'

const MAX_RETRIES   = 5
const BASE_DELAY_MS = 1000

type Callbacks = {
  onNode:  (node: GraphNode) => void
  onEdge:  (edge: GraphEdge) => void
  onDone:  (summary: GraphDoneEvent) => void
  onError: (msg: string) => void
}

export type GraphStreamState = 'idle' | 'connecting' | 'streaming' | 'done' | 'error' | 'retrying'

export function useGraphStream() {
  const [gState, setGState]       = useState<GraphStreamState>('idle')
  const [retryCount, setRetry]    = useState(0)
  const firstNodeRef               = useRef(false)
  const wsRef                      = useRef<WebSocket | null>(null)
  const callbacksRef               = useRef<Callbacks | null>(null)
  const retryTimerRef              = useRef<ReturnType<typeof setTimeout> | null>(null)
  const activeRef                  = useRef(false)

  const connect = useCallback((callbacks: Callbacks, attempt = 0) => {
    callbacksRef.current = callbacks
    activeRef.current    = true
    firstNodeRef.current = false

    setGState('connecting')
    setRetry(attempt)

    const ws = new WebSocket(`${env.wsBaseUrl}/graph/stream`)
    wsRef.current = ws

    ws.onopen = () => setGState('streaming')

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data as string)
        if (msg.event === 'node') {
          if (!firstNodeRef.current) firstNodeRef.current = true
          callbacksRef.current?.onNode(msg as GraphNode)
        } else if (msg.event === 'edge') {
          callbacksRef.current?.onEdge(msg as GraphEdge)
        } else if (msg.event === 'done') {
          // Server is done — prevent onclose from triggering a reconnect
          activeRef.current = false
          setGState('done')
          callbacksRef.current?.onDone(msg as GraphDoneEvent)
        }
      } catch {
        // Non-JSON frame — ignore
      }
    }

    ws.onerror = () => {
      callbacksRef.current?.onError('WebSocket error')
    }

    ws.onclose = () => {
      if (!activeRef.current) return
      if (attempt < MAX_RETRIES) {
        const delay = BASE_DELAY_MS * Math.pow(2, attempt)
        setGState('retrying')
        retryTimerRef.current = setTimeout(() => {
          if (activeRef.current && callbacksRef.current) {
            connect(callbacksRef.current, attempt + 1)
          }
        }, delay)
      } else {
        setGState('error')
        callbacksRef.current?.onError('Graph stream disconnected after max retries')
      }
    }
  }, [])

  const disconnect = useCallback(() => {
    activeRef.current = false
    if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
    wsRef.current?.close()
    wsRef.current = null
    setGState('idle')
    setRetry(0)
  }, [])

  // Clean up on unmount
  useEffect(() => () => { disconnect() }, [disconnect])

  return {
    gState,
    retryCount,
    firstNodeArrived: firstNodeRef,
    connect,
    disconnect,
  }
}
