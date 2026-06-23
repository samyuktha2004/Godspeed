import { useCallback, useRef, useState } from 'react'
import { ssePost } from '@/lib/http'
import type { QueryInput, SSEEventMap, SSEEventName } from '@/types/api'

const TIMEOUT_MS = 30_000

type Callbacks = {
  [K in SSEEventName]?: (data: SSEEventMap[K]) => void
}

export type StreamState = 'idle' | 'loading' | 'streaming' | 'complete' | 'error'

export function useSSEStream() {
  const [state, setState]             = useState<StreamState>('idle')
  const [error, setError]             = useState<string | null>(null)
  const [firstEventArrived, setFirstEventArrived] = useState(false)
  const firstEventRef                 = useRef(false)
  const completedRef                  = useRef(false)
  const abortRef                      = useRef<AbortController | null>(null)

  const stream = useCallback(
    async (input: QueryInput, callbacks: Callbacks) => {
      // Cancel any in-flight request
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      firstEventRef.current = false
      completedRef.current  = false
      setState('loading')
      setFirstEventArrived(false)
      setError(null)

      // Hard timeout — fire error event if backend stalls
      const timeoutId = setTimeout(() => {
        controller.abort()
        setError('Query timed out after 30 seconds')
        setState('error')
        callbacks.error?.({ message: 'Query timed out after 30 seconds' })
      }, TIMEOUT_MS)

      try {
        const res = await ssePost('/agent/query', input, controller.signal)
        const reader = res.body!.getReader()
        const decoder = new TextDecoder()

        let buffer          = ''
        let currentEvent: SSEEventName = 'answer_chunk'
        let malformedCount  = 0
        const MALFORMED_THRESHOLD = 5

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })

          // SSE messages are separated by double newline
          const messages = buffer.split('\n\n')
          buffer = messages.pop() ?? ''

          for (const message of messages) {
            if (!message.trim()) continue

            let eventName: SSEEventName = currentEvent
            let dataLine = ''

            for (const line of message.split('\n')) {
              if (line.startsWith('event: ')) {
                eventName = line.slice(7).trim() as SSEEventName
              } else if (line.startsWith('data: ')) {
                dataLine = line.slice(6)
              }
            }

            if (!dataLine) continue

            // First event received — transition loading → streaming
            if (!firstEventRef.current) {
              firstEventRef.current = true
              setFirstEventArrived(true)
              setState('streaming')
              clearTimeout(timeoutId)
            }

            try {
              const data = JSON.parse(dataLine)
              malformedCount = 0
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              ;(callbacks as any)[eventName]?.(data)

              if (eventName === 'done') {
                completedRef.current = true
                setState('complete')
              } else if (eventName === 'error') {
                setError(data.message)
                setState('error')
              }
            } catch {
              malformedCount++
              if (malformedCount >= MALFORMED_THRESHOLD) {
                const msg = 'Stream error — received malformed data from server'
                setError(msg)
                setState('error')
                callbacks.error?.({ message: msg })
                return
              }
            }
          }
        }

        // Stream ended without a done event — treat as incomplete
        if (firstEventRef.current && !completedRef.current) {
          setError('Connection dropped — answer may be incomplete')
          setState('error')
          callbacks.error?.({ message: 'Connection dropped — answer may be incomplete' })
        }
      } catch (err) {
        if ((err as Error).name === 'AbortError') return
        const message = err instanceof Error ? err.message : 'Unknown error'
        setError(message)
        setState('error')
        callbacks.error?.({ message })
      } finally {
        clearTimeout(timeoutId)
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [],
  )

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    setState('idle')
  }, [])

  return {
    state,
    error,
    firstEventArrived,
    stream,
    cancel,
  }
}
