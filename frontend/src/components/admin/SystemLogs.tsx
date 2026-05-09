import { useEffect, useRef, useState } from 'react'
import { env } from '@/config/env'
import { cn } from '@/lib/utils'

interface LogLine {
  time:       string
  level:      'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'
  logger:     string
  request_id: string
  message:    string
  [key: string]: unknown
}

const LEVEL_STYLES: Record<LogLine['level'], string> = {
  DEBUG:    'text-stone-400',
  INFO:     'text-blue-500',
  WARNING:  'text-amber-500',
  ERROR:    'text-red-500',
  CRITICAL: 'text-red-700 font-bold',
}

const LEVEL_BG: Record<LogLine['level'], string> = {
  DEBUG:    '',
  INFO:     '',
  WARNING:  '',
  ERROR:    'bg-red-50 dark:bg-red-950/20',
  CRITICAL: 'bg-red-100 dark:bg-red-950/40',
}

const MAX_LINES = 500

export function SystemLogs() {
  const [lines,      setLines]      = useState<LogLine[]>([])
  const [connected,  setConnected]  = useState(false)
  const [paused,     setPaused]     = useState(false)
  const [filter,     setFilter]     = useState<LogLine['level'] | 'ALL'>('ALL')
  const [search,     setSearch]     = useState('')
  const bottomRef                   = useRef<HTMLDivElement>(null)
  const pausedRef                   = useRef(false)
  const wsRef                       = useRef<WebSocket | null>(null)

  pausedRef.current = paused

  useEffect(() => {
    const wsUrl = env.apiBaseUrl.replace(/^http/, 'ws') + '/ws/logs'
    const ws    = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen  = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onerror = () => setConnected(false)

    ws.onmessage = (e) => {
      if (pausedRef.current) return
      try {
        const line = JSON.parse(e.data) as LogLine
        setLines((prev) => {
          const next = [...prev, line]
          return next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next
        })
      } catch {
        // non-JSON log line — show as raw
        setLines((prev) => {
          const raw: LogLine = {
            time: new Date().toISOString(), level: 'INFO',
            logger: 'raw', request_id: '-', message: e.data,
          }
          const next = [...prev, raw]
          return next.length > MAX_LINES ? next.slice(next.length - MAX_LINES) : next
        })
      }
    }

    return () => ws.close()
  }, [])

  // Auto-scroll when not paused
  useEffect(() => {
    if (!paused) bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines, paused])

  const visible = lines.filter((l) => {
    if (filter !== 'ALL' && l.level !== filter) return false
    if (search && !l.message.toLowerCase().includes(search.toLowerCase()) &&
        !l.logger.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  function clearLogs() { setLines([]) }

  return (
    <div className="flex flex-col gap-3">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1.5">
          <span className={cn('h-2 w-2 rounded-full', connected ? 'bg-green-500' : 'bg-red-500')} />
          <span className="text-xs text-stone-500">{connected ? 'Live' : 'Disconnected'}</span>
        </div>

        <div className="flex flex-1 items-center gap-2">
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter logs…"
            className="h-8 flex-1 rounded-lg border border-surface-subtle bg-white px-3 text-xs dark:bg-stone-900 min-w-0"
          />

          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value as typeof filter)}
            className="h-8 rounded-lg border border-surface-subtle bg-white px-2 text-xs dark:bg-stone-900"
          >
            {(['ALL', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] as const).map((l) => (
              <option key={l} value={l}>{l}</option>
            ))}
          </select>
        </div>

        <button
          onClick={() => setPaused((p) => !p)}
          className={cn(
            'rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
            paused
              ? 'bg-amber-100 text-amber-700 hover:bg-amber-200 dark:bg-amber-900/30 dark:text-amber-400'
              : 'bg-stone-100 text-stone-600 hover:bg-stone-200 dark:bg-stone-800 dark:text-stone-400',
          )}
        >
          {paused ? 'Resume' : 'Pause'}
        </button>

        <button
          onClick={clearLogs}
          className="rounded-lg px-3 py-1.5 text-xs font-medium text-stone-500 hover:bg-stone-100 dark:hover:bg-stone-800"
        >
          Clear
        </button>
      </div>

      {/* Log terminal */}
      <div className="h-[500px] overflow-y-auto rounded-xl border border-surface-subtle bg-stone-950 p-4 font-mono text-xs text-stone-300">
        {visible.length === 0 ? (
          <p className="text-stone-600">
            {connected ? 'Waiting for log events…' : 'WebSocket not connected — check that the backend is running.'}
          </p>
        ) : (
          visible.map((l, i) => (
            <div key={i} className={cn('mb-0.5 flex gap-2 leading-5', LEVEL_BG[l.level])}>
              <span className="shrink-0 text-stone-600">
                {new Date(l.time).toLocaleTimeString()}
              </span>
              <span className={cn('w-16 shrink-0', LEVEL_STYLES[l.level])}>{l.level}</span>
              <span className="shrink-0 text-stone-500">{l.logger}</span>
              {l.request_id !== '-' && (
                <span className="shrink-0 text-stone-600">[{l.request_id.slice(0, 8)}]</span>
              )}
              <span className="min-w-0 break-all">{l.message}</span>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>

      <p className="text-right text-xs text-stone-400">{visible.length} lines shown (max {MAX_LINES})</p>
    </div>
  )
}
