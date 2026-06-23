import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearch, useNavigate } from '@tanstack/react-router'
import { useAuthStore } from '@/stores/authStore'
import { useUIStore } from '@/stores/uiStore'
import { useSSEStream } from '@/hooks/useSSEStream'
import { useGraphStream } from '@/hooks/useGraphStream'
import { HallucinationWarning } from '@/components/common/HallucinationWarning'
import { TimeoutError } from '@/components/common/TimeoutError'
import { NetworkRetry } from '@/components/common/NetworkRetry'
import { SearchBox } from '@/components/query/SearchBox'
import { AgentBadges, type AgentStatus } from '@/components/results/AgentBadges'
import { Answer } from '@/components/results/Answer'
import { Citations } from '@/components/results/Citations'
import { RelatedDocs } from '@/components/results/RelatedDocs'
import { FollowUp } from '@/components/results/FollowUp'
import { KnowledgeGraph } from '@/components/results/KnowledgeGraph'
import { GraphNodeTooltip } from '@/components/results/GraphNodeTooltip'
import { GraphNodeDetailPanel } from '@/components/results/GraphNodeDetailPanel'
import { QueryFeedback } from '@/components/results/QueryFeedback'
import { ShareResults } from '@/components/results/ShareResults'
import { NoResultsState } from '@/components/common/NoResultsState'
import { cn } from '@/lib/utils'
import type {
  AgentTask, RetrievedChunk, GuardrailResult, ExecutionPlan,
  GraphNode, GraphEdge,
} from '@/types/api'

type Tab = 'graph' | 'answer'

const QR_PREFIX   = 'gs_qr_'
const QR_INDEX    = 'gs_qr_index'   // JSON array of keys in LRU order (oldest first)
const QR_MAX      = 10

function cacheWrite(key: string, payload: string) {
  try {
    sessionStorage.setItem(key, payload)
    const raw   = sessionStorage.getItem(QR_INDEX)
    const index: string[] = raw ? JSON.parse(raw) : []
    const next  = [...index.filter((k) => k !== key), key]
    if (next.length > QR_MAX) {
      const evicted = next.splice(0, next.length - QR_MAX)
      evicted.forEach((k) => sessionStorage.removeItem(k))
    }
    sessionStorage.setItem(QR_INDEX, JSON.stringify(next))
  } catch { /* quota exceeded — skip caching */ }
}

interface Exchange {
  id: string
  query: string
  answer: string
  citations: RetrievedChunk[]
  plan: AgentTask[]
}

export function ResultsPage() {
  const user       = useAuthStore((s) => s.user)
  const navigate   = useNavigate()
  const { graphCollapsed, toggleGraphCollapsed } = useUIStore()
  const sessionRef = useRef(crypto.randomUUID())
  const savedRef   = useRef(false)
  const { q: initialQuery, qid: initialQid, fresh: forceRun } = useSearch({ from: '/query' })

  // ── Conversation history ─────────────────────────────────────────────────────
  const [exchanges, setExchanges] = useState<Exchange[]>([])

  // ── SSE state (current streaming exchange) ───────────────────────────────────
  const [plan, setPlan]               = useState<AgentTask[]>([])
  const [agentStatuses, setStatuses]  = useState<Record<string, AgentStatus>>({})
  const [answerText, setAnswerText]   = useState('')
  const [citations, setCitations]     = useState<RetrievedChunk[]>([])
  const [guardrail, setGuardrail]     = useState<GuardrailResult | null>(null)
  const [currentQuery, setCurrentQuery] = useState('')
  const [queryId, setQueryId]           = useState('')
  const [shareOpen, setShareOpen]       = useState(false)

  // Refs for reading current values inside runQuery without stale closure.
  // Updated directly in callbacks — no useEffect sync needed.
  const answerTextRef   = useRef('')
  const citationsRef    = useRef<RetrievedChunk[]>([])
  const planRef         = useRef<AgentTask[]>([])
  const currentQueryRef = useRef('')

  // ── Graph state ─────────────────────────────────────────────────────────────
  const [graphNodes, setGraphNodes]     = useState<GraphNode[]>([])
  const [graphEdges, setGraphEdges]     = useState<GraphEdge[]>([])
  const [hoveredNode, setHoveredNode]   = useState<GraphNode | null>(null)
  const [hoverPos, setHoverPos]         = useState({ x: 0, y: 0 })
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const nodesAccRef = useRef<GraphNode[]>([])
  const edgesAccRef = useRef<GraphEdge[]>([])

  // ── Mobile tab ──────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab]       = useState<Tab>('graph')
  const [graphMaximized, setGraphMaximized] = useState(false)

  // ── Hooks ───────────────────────────────────────────────────────────────────
  const { state, error, firstEventArrived, stream } = useSSEStream()
  const { gState, retryCount, connect, disconnect } = useGraphStream()

  useEffect(() => {
    if (gState === 'error' && !graphCollapsed) toggleGraphCollapsed()
  }, [gState]) // eslint-disable-line react-hooks/exhaustive-deps

  const reconnectGraph = useCallback(() => {
    nodesAccRef.current = []
    edgesAccRef.current = []
    setGraphNodes([])
    setGraphEdges([])
    disconnect()
    connect({
      onNode: (node) => {
        nodesAccRef.current = [...nodesAccRef.current, node]
        setGraphNodes([...nodesAccRef.current])
      },
      onEdge: (edge) => {
        edgesAccRef.current = [...edgesAccRef.current, edge]
        setGraphEdges([...edgesAccRef.current])
      },
      onDone:  () => {},
      onError: () => {},
    })
  }, [connect, disconnect])

  // ── Query runner ─────────────────────────────────────────────────────────────
  const runQuery = useCallback(
    async (query: string) => {
      // Push completed exchange to history before resetting.
      // Read directly from refs — they're kept current by the callbacks below.
      if (answerTextRef.current && currentQueryRef.current) {
        setExchanges((prev) => [
          ...prev,
          {
            id:        crypto.randomUUID(),
            query:     currentQueryRef.current,
            answer:    answerTextRef.current,
            citations: citationsRef.current,
            plan:      planRef.current,
          },
        ])
      }

      // Reset all streaming state and refs together
      savedRef.current      = false
      answerTextRef.current  = ''
      citationsRef.current   = []
      planRef.current        = []
      currentQueryRef.current = query

      setPlan([])
      setStatuses({})
      setAnswerText('')
      setCitations([])
      setGuardrail(null)
      setCurrentQuery(query)
      setQueryId(crypto.randomUUID())
      setShareOpen(false)
      setActiveTab('graph')
      setSelectedNode(null)

      reconnectGraph()

      await stream(
        { query, team_id: user?.team_id ?? 'default', session_id: sessionRef.current },
        {
          plan_ready: (data: ExecutionPlan) => {
            planRef.current = data.tasks
            setPlan(data.tasks)
            setStatuses(
              Object.fromEntries(
                data.tasks.map((t) => [t.agent, { agent: t.agent, state: 'pending' }]),
              ),
            )
          },
          agent_started: ({ agent }) => {
            setStatuses((prev) => ({ ...prev, [agent]: { agent, state: 'active' } }))
          },
          agent_done: (result) => {
            setStatuses((prev) => ({
              ...prev,
              [result.agent]: {
                agent:      result.agent,
                state:      'done',
                confidence: result.retrieval_confidence,
              },
            }))
          },
          citations: ({ chunks }) => {
            citationsRef.current = chunks
            setCitations(chunks)
          },
          answer_chunk: ({ chunk }) => {
            answerTextRef.current += chunk
            setAnswerText((prev) => prev + chunk)
          },
          guardrail_result: (g) => {
            setGuardrail(g)
          },
        },
      )
    },
    [stream, reconnectGraph, user],
  )

  const handleNodeHover = useCallback(
    (node: GraphNode | null, x: number, y: number) => {
      setHoveredNode(node)
      setHoverPos({ x, y })
    },
    [],
  )

  const handleNodeClick = useCallback((node: GraphNode) => {
    setSelectedNode(node)
  }, [])

  const runQueryRef = useRef(runQuery)
  runQueryRef.current = runQuery
  const textKey = (q: string) => QR_PREFIX + 'q:' + q

  const restoreFromCache = (raw: string): boolean => {
    try {
      const { query, answer, citations: cc } = JSON.parse(raw)
      setCurrentQuery(query)
      currentQueryRef.current = query
      setAnswerText(answer)
      answerTextRef.current = answer
      setCitations(cc ?? [])
      citationsRef.current = cc ?? []
      savedRef.current = true
      return true
    } catch { return false }
  }

  const lastParamKeyRef = useRef('')

  useEffect(() => {
    const paramKey = `${initialQid ?? ''}|${initialQuery ?? ''}|${String(forceRun)}`
    if (lastParamKeyRef.current === paramKey) return
    lastParamKeyRef.current = paramKey

    if (!forceRun) {
      if (initialQid) {
        try {
          const raw = sessionStorage.getItem(QR_PREFIX + initialQid)
          if (raw && restoreFromCache(raw)) return
        } catch { /* ignore */ }
      }
      if (initialQuery) {
        try {
          const raw = sessionStorage.getItem(textKey(initialQuery))
          if (raw && restoreFromCache(raw)) return
        } catch { /* ignore */ }
      }
    }
    if (initialQuery) runQueryRef.current(initialQuery)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuery, initialQid, forceRun])

  // Cache completed result and update URL to ?qid=
  useEffect(() => {
    if (state !== 'complete' || !currentQuery || !answerText || savedRef.current) return
    savedRef.current = true
    const qid     = sessionRef.current
    const payload = JSON.stringify({ query: currentQuery, answer: answerText, citations })
    cacheWrite(QR_PREFIX + qid, payload)
    cacheWrite(textKey(currentQuery), payload)
    navigate({ to: '/query', search: { qid, q: undefined, fresh: false }, replace: true })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state])

  // Scroll to bottom when new exchange added or answer streams in
  const bottomRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [exchanges.length, answerText])

  // ── Derived ─────────────────────────────────────────────────────────────────
  const isLoading   = state === 'loading'
  const isStreaming = state === 'streaming'
  const isComplete  = state === 'complete'
  const isError     = state === 'error'
  const isActive    = isLoading || isStreaming
  const hasData     = firstEventArrived

  const graphHasContent  = graphNodes.length > 0
  const answerHasContent = !!answerText || plan.length > 0

  return (
    <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-4 py-8">

      {/* Search bar */}
      <SearchBox
        value={currentQuery || (initialQuery ?? '')}
        onSubmit={runQuery}
        disabled={isActive}
      />

      {/* Idle home state */}
      {state === 'idle' && !currentQuery && exchanges.length === 0 && (
        <div className="flex flex-1 items-center justify-center">
          <p className="text-sm text-stone-400">Ask a question to get started.</p>
        </div>
      )}

      {/* ── Results layout ─────────────────────────────────────────────── */}
      {(currentQuery || exchanges.length > 0) && (
        <>
          {/* Mobile tab bar */}
          <div className="flex rounded-xl border border-surface-subtle bg-stone-50 p-1 dark:bg-stone-800/50 lg:hidden">
            <button
              onClick={() => setActiveTab('graph')}
              className={cn(
                'flex flex-1 items-center justify-center gap-2 rounded-lg py-2 text-sm font-medium transition-colors',
                activeTab === 'graph'
                  ? 'bg-white text-stone-900 shadow-sm dark:bg-stone-700 dark:text-stone-100'
                  : 'text-stone-500 hover:text-stone-700 dark:text-stone-400',
              )}
            >
              Graph
              {graphHasContent && (
                <span className="rounded-full bg-brand/10 px-1.5 py-0.5 text-xs font-semibold text-brand">
                  {graphNodes.length}
                </span>
              )}
            </button>
            <button
              onClick={() => setActiveTab('answer')}
              disabled={!hasData && exchanges.length === 0}
              className={cn(
                'flex flex-1 items-center justify-center gap-2 rounded-lg py-2 text-sm font-medium transition-colors',
                !hasData && exchanges.length === 0
                  ? 'cursor-not-allowed text-stone-300 dark:text-stone-600'
                  : activeTab === 'answer'
                  ? 'bg-white text-stone-900 shadow-sm dark:bg-stone-700 dark:text-stone-100'
                  : 'text-stone-500 hover:text-stone-700 dark:text-stone-400',
              )}
            >
              Answer
              {hasData && isActive && answerHasContent && (
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand" />
              )}
            </button>
          </div>

          {/* Two-column grid */}
          <div className={cn(
            'flex flex-col gap-6 lg:grid lg:items-start lg:gap-8',
            graphCollapsed ? 'lg:grid-cols-1' : 'lg:grid-cols-[1fr_380px]',
          )}>

            {/* ── Left: conversation column ─────────────────────────────────── */}
            <div className={cn(
              'flex flex-col gap-8',
              activeTab === 'graph' && 'hidden lg:flex',
            )}>
              {graphCollapsed && (
                <button
                  onClick={toggleGraphCollapsed}
                  className="hidden lg:inline-flex w-fit items-center gap-1.5 rounded-full border border-surface-subtle bg-stone-50 px-3 py-1 text-xs text-stone-500 hover:bg-stone-100 dark:bg-stone-800/60 dark:hover:bg-stone-700"
                >
                  ▶ Show graph
                </button>
              )}

              {/* ── Completed past exchanges ─────────────────────────────── */}
              {exchanges.map((ex) => (
                <div key={ex.id} className="flex flex-col gap-4 border-b border-surface-subtle pb-8">
                  <p className="text-sm font-semibold text-stone-500">{ex.query}</p>
                  <Answer text={ex.answer} />
                  {ex.citations.length > 0 && <Citations chunks={ex.citations} />}
                </div>
              ))}

              {/* ── Current streaming exchange ────────────────────────────── */}
              {currentQuery && (
                <div className="flex flex-col gap-4">
                  {exchanges.length > 0 && (
                    <p className="text-sm font-semibold text-stone-700 dark:text-stone-300">
                      {currentQuery}
                    </p>
                  )}

                  {isActive && !hasData && (
                    <div className="flex items-center gap-2 text-sm text-stone-400">
                      <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-stone-200 border-t-stone-500" />
                      Thinking…
                    </div>
                  )}

                  {plan.length > 0 && (
                    <AgentBadges plan={plan} statuses={agentStatuses} />
                  )}

                  {answerText && <Answer text={answerText} />}

                  {isComplete && !answerText && citations.length === 0 && (
                    <NoResultsState query={currentQuery} />
                  )}

                  {guardrail?.escalate && <HallucinationWarning />}

                  {isError && !answerText && (
                    <TimeoutError
                      message={error ?? undefined}
                      onRetry={() => runQuery(currentQuery)}
                    />
                  )}

                  {isError && answerText && error?.includes('incomplete') && (
                    <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
                      <span aria-hidden>⚠</span>
                      Answer may be incomplete — connection dropped mid-stream.
                      <button onClick={() => runQuery(currentQuery)} className="ml-auto shrink-0 underline">
                        Retry
                      </button>
                    </div>
                  )}

                  {citations.length > 0 && <Citations chunks={citations} />}

                  {isComplete && citations.length > 3 && (
                    <RelatedDocs chunks={citations.slice(3)} />
                  )}

                  {isComplete && (
                    <div className="flex items-center justify-between gap-4">
                      <QueryFeedback queryId={queryId} />
                      <button
                        onClick={() => setShareOpen(true)}
                        className="shrink-0 text-xs text-stone-400 underline hover:text-stone-600"
                      >
                        Share
                      </button>
                    </div>
                  )}
                </div>
              )}

              <div ref={bottomRef} />

              {(isComplete || exchanges.length > 0) && (
                <FollowUp onSubmit={runQuery} disabled={isActive} />
              )}
            </div>

            {/* ── Right: graph panel ───────────────────────────────────────── */}
            <div className={cn(
              'flex flex-col overflow-hidden rounded-xl border border-surface-subtle',
              activeTab === 'answer' ? 'hidden lg:flex' : 'flex',
              graphCollapsed && 'lg:hidden',
              graphMaximized
                ? 'fixed inset-0 z-50 rounded-none border-0 bg-white dark:bg-stone-950'
                : 'h-[440px]',
            )}>
              <div className="flex shrink-0 items-center gap-2 border-b border-surface-subtle px-3 py-2">
                <span className="flex-1 text-xs font-semibold uppercase tracking-wide text-stone-400">
                  Knowledge Graph
                </span>
                {graphNodes.length > 0 && (
                  <span className="text-xs text-stone-400">
                    {graphNodes.length} nodes · {graphEdges.length} edges
                  </span>
                )}
                <button
                  onClick={() => setGraphMaximized((m) => !m)}
                  title={graphMaximized ? 'Exit fullscreen' : 'Fullscreen'}
                  className="rounded p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-600 dark:hover:bg-stone-800 dark:hover:text-stone-300"
                  aria-label={graphMaximized ? 'Exit fullscreen' : 'Fullscreen'}
                >
                  {graphMaximized ? '⤡' : '⤢'}
                </button>
                <button
                  onClick={toggleGraphCollapsed}
                  title="Collapse graph"
                  className="hidden rounded p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-600 dark:hover:bg-stone-800 dark:hover:text-stone-300 lg:block"
                  aria-label="Collapse graph"
                >
                  ◀
                </button>
              </div>

              <KnowledgeGraph
                nodes={graphNodes}
                edges={graphEdges}
                streaming={isActive}
                onNodeClick={handleNodeClick}
                onNodeHover={handleNodeHover}
                className="flex-1"
              />

              <div className="flex shrink-0 items-center gap-2 border-t border-surface-subtle px-3 py-2">
                {gState === 'done' && (
                  <button
                    onClick={reconnectGraph}
                    className="ml-auto text-xs text-stone-400 hover:text-stone-600 dark:hover:text-stone-300"
                    title="Reload graph with latest data"
                  >
                    ↻ Refresh
                  </button>
                )}
                {gState === 'retrying' && <NetworkRetry attempt={retryCount + 1} />}
              </div>

              {gState === 'error' && (
                <div className="flex shrink-0 items-center justify-between border-t border-stone-200 bg-stone-50 px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-800/40">
                  <span className="text-stone-500 dark:text-stone-400">
                    Couldn't load the knowledge graph.
                  </span>
                  <button
                    onClick={reconnectGraph}
                    className="ml-4 shrink-0 rounded bg-stone-200 px-3 py-1 text-xs font-medium text-stone-700 hover:bg-stone-300 dark:bg-stone-700 dark:text-stone-300 dark:hover:bg-stone-600"
                  >
                    Try again
                  </button>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      <GraphNodeTooltip node={hoveredNode} x={hoverPos.x} y={hoverPos.y} />

      <ShareResults
        query={currentQuery}
        open={shareOpen}
        onClose={() => setShareOpen(false)}
      />

      <GraphNodeDetailPanel
        node={selectedNode}
        teamId={user?.team_id ?? 'default'}
        onClose={() => setSelectedNode(null)}
        onAskAbout={(q) => runQuery(q)}
      />
    </div>
  )
}
