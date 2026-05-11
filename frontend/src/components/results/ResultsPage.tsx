import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearch } from '@tanstack/react-router'
import { useAuthStore } from '@/stores/authStore'
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

export function ResultsPage() {
  const user       = useAuthStore((s) => s.user)
  const sessionRef = useRef(crypto.randomUUID())
  const { q: initialQuery } = useSearch({ from: '/query' })

  // ── SSE state ───────────────────────────────────────────────────────────────
  const [plan, setPlan]               = useState<AgentTask[]>([])
  const [agentStatuses, setStatuses]  = useState<Record<string, AgentStatus>>({})
  const [answerText, setAnswerText]   = useState('')
  const [citations, setCitations]     = useState<RetrievedChunk[]>([])
  const [guardrail, setGuardrail]     = useState<GuardrailResult | null>(null)
  const [currentQuery, setCurrentQuery] = useState('')
  const [queryId, setQueryId]           = useState('')
  const [shareOpen, setShareOpen]       = useState(false)

  // ── Graph state ─────────────────────────────────────────────────────────────
  const [graphNodes, setGraphNodes]     = useState<GraphNode[]>([])
  const [graphEdges, setGraphEdges]     = useState<GraphEdge[]>([])
  const [hoveredNode, setHoveredNode]   = useState<GraphNode | null>(null)
  const [hoverPos, setHoverPos]         = useState({ x: 0, y: 0 })
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  // Accumulated in refs to avoid setState on every 50ms node message
  const nodesAccRef = useRef<GraphNode[]>([])
  const edgesAccRef = useRef<GraphEdge[]>([])

  // ── Mobile tab ──────────────────────────────────────────────────────────────
  const [activeTab, setActiveTab] = useState<Tab>('graph')

  // ── Hooks ───────────────────────────────────────────────────────────────────
  const { state, error, firstEventArrived, stream } = useSSEStream()
  const { gState, retryCount, connect, disconnect } = useGraphStream()

  // ── Shared graph reconnect ───────────────────────────────────────────────────
  // Used both by runQuery (new query) and the standalone "Reload / Try again" buttons.
  // Clears accumulated state then opens a fresh WS to /graph/stream.
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
      // Reset all state for the new query
      setPlan([])
      setStatuses({})
      setAnswerText('')
      setCitations([])
      setGuardrail(null)
      setCurrentQuery(query)
      setQueryId(crypto.randomUUID())
      setShareOpen(false)
      setActiveTab('graph') // always start on graph tab so user sees it populate
      setSelectedNode(null)

      reconnectGraph()

      await stream(
        { query, team_id: user?.team_id ?? 'default', session_id: sessionRef.current },
        {
          plan_ready: (data: ExecutionPlan) => {
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
            setCitations(chunks)
          },
          answer_chunk: ({ chunk }) => {
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

  // Auto-fire from URL ?q= on mount
  const runQueryRef = useRef(runQuery)
  runQueryRef.current = runQuery
  useEffect(() => {
    if (initialQuery) runQueryRef.current(initialQuery)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // ── Derived ─────────────────────────────────────────────────────────────────
  const isLoading   = state === 'loading'
  const isStreaming = state === 'streaming'
  const isComplete  = state === 'complete'
  const isError     = state === 'error'
  const isActive    = isLoading || isStreaming
  const hasData     = firstEventArrived.current  // set when first SSE event arrives

  // ── Tab indicators ──────────────────────────────────────────────────────────
  const graphHasContent  = graphNodes.length > 0
  const answerHasContent = !!answerText || plan.length > 0

  return (
    <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-4 py-8">

      {/* Search bar — always visible */}
      <SearchBox
        onSubmit={runQuery}
        disabled={isActive}
        defaultValue={initialQuery ?? ''}
      />

      {/* Idle home state — no query yet */}
      {state === 'idle' && !currentQuery && (
        <div className="flex flex-1 items-center justify-center">
          <p className="text-sm text-stone-400">Ask a question to get started.</p>
        </div>
      )}

      {/* ── Results layout — mounted immediately when query fires ─────────── */}
      {currentQuery && (
        <>
          {/* Mobile tab bar — hidden on lg where both columns are visible */}
          {/* Answer tab is disabled (grey) until first SSE event arrives */}
          <div className="flex rounded-xl border border-surface-subtle bg-stone-50 p-1 dark:bg-stone-800/50 lg:hidden">
            {/* Graph tab — always accessible; shows animation even before nodes arrive */}
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

            {/* Answer tab — disabled (grey, not clickable) until first SSE event */}
            <button
              onClick={() => setActiveTab('answer')}
              disabled={!hasData}
              className={cn(
                'flex flex-1 items-center justify-center gap-2 rounded-lg py-2 text-sm font-medium transition-colors',
                !hasData
                  ? 'cursor-not-allowed text-stone-300 dark:text-stone-600'
                  : activeTab === 'answer'
                  ? 'bg-white text-stone-900 shadow-sm dark:bg-stone-700 dark:text-stone-100'
                  : 'text-stone-500 hover:text-stone-700 dark:text-stone-400',
              )}
            >
              Answer
              {/* Pulsing dot only once answer has data and is still streaming */}
              {hasData && isActive && answerHasContent && (
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand" />
              )}
            </button>
          </div>

          {/* Two-column grid — graph right, answer left */}
          <div className="flex flex-col gap-6 lg:grid lg:grid-cols-[1fr_380px] lg:items-start lg:gap-8">

            {/* ── Left: answer column ──────────────────────────────────────── */}
            <div className={cn(
              'flex flex-col gap-6',
              activeTab === 'graph' && 'hidden lg:flex',
            )}>

              {/* Thinking indicator — before any SSE event arrives */}
              {isActive && !hasData && (
                <div className="flex items-center gap-2 text-sm text-stone-400">
                  <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-stone-200 border-t-stone-500" />
                  Thinking…
                </div>
              )}

              {/* Agent progress badges */}
              {plan.length > 0 && (
                <AgentBadges plan={plan} statuses={agentStatuses} />
              )}

              {/* Streaming answer */}
              {answerText && <Answer text={answerText} />}

              {/* Complete with no answer */}
              {isComplete && !answerText && <NoResultsState query={currentQuery} />}

              {/* Guardrail escalation */}
              {guardrail?.escalate && <HallucinationWarning />}

              {/* Hard error — no answer at all */}
              {isError && !answerText && (
                <TimeoutError
                  message={error ?? undefined}
                  onRetry={() => runQuery(currentQuery)}
                />
              )}

              {/* Soft error — answer cut short mid-stream */}
              {isError && answerText && error?.includes('incomplete') && (
                <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
                  <span aria-hidden>⚠</span>
                  Answer may be incomplete — connection dropped mid-stream.
                  <button
                    onClick={() => runQuery(currentQuery)}
                    className="ml-auto shrink-0 underline"
                  >
                    Retry
                  </button>
                </div>
              )}

              {/* Citations */}
              {citations.length > 0 && <Citations chunks={citations} />}

              {/* Related docs (overflow citations) */}
              {isComplete && citations.length > 3 && (
                <RelatedDocs chunks={citations.slice(3)} />
              )}

              {/* Footer actions */}
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

              {isComplete && <FollowUp onSubmit={runQuery} />}
            </div>

            {/* ── Right: graph column — always mounted ─────────────────────── */}
            {/* CSS hides it on mobile when answer tab is active; on desktop always visible */}
            <div className={cn(
              'flex flex-col gap-2',
              activeTab === 'answer' && 'hidden lg:flex',
            )}>
              <KnowledgeGraph
                nodes={graphNodes}
                edges={graphEdges}
                streaming={isActive}
                onNodeClick={handleNodeClick}
                onNodeHover={handleNodeHover}
              />

              {/* Graph footer: node count + refresh/reload controls */}
              <div className="flex items-center gap-2">
                {graphNodes.length > 0 && (
                  <p className="flex-1 text-xs text-stone-400">
                    {graphNodes.length} node{graphNodes.length !== 1 ? 's' : ''}
                    {' · '}
                    {graphEdges.length} connection{graphEdges.length !== 1 ? 's' : ''}
                  </p>
                )}

                {/* Refresh button — available when graph finished streaming (data may have updated) */}
                {gState === 'done' && (
                  <button
                    onClick={reconnectGraph}
                    className="ml-auto shrink-0 text-xs text-stone-400 hover:text-stone-600 dark:hover:text-stone-300"
                    title="Reload graph with latest data"
                  >
                    ↻ Refresh graph
                  </button>
                )}
              </div>

              {/* Auto-retry indicator */}
              {gState === 'retrying' && (
                <NetworkRetry attempt={retryCount + 1} />
              )}

              {/* Manual reload after max retries exhausted */}
              {gState === 'error' && (
                <div className="flex items-center justify-between rounded-lg border border-stone-200 bg-stone-50 px-4 py-3 text-sm dark:border-stone-700 dark:bg-stone-800/40">
                  <span className="text-stone-600 dark:text-stone-400">
                    Couldn't load the knowledge graph.
                  </span>
                  <button
                    onClick={reconnectGraph}
                    className="ml-4 shrink-0 rounded bg-stone-200 px-3 py-1.5 text-xs font-medium text-stone-700 hover:bg-stone-300 dark:bg-stone-700 dark:text-stone-300 dark:hover:bg-stone-600"
                  >
                    Try again
                  </button>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* Tooltip — document-level fixed positioning */}
      <GraphNodeTooltip node={hoveredNode} x={hoverPos.x} y={hoverPos.y} />

      {/* Share modal */}
      <ShareResults
        query={currentQuery}
        open={shareOpen}
        onClose={() => setShareOpen(false)}
      />

      {/* Node detail slide-in panel */}
      <GraphNodeDetailPanel
        node={selectedNode}
        teamId={user?.team_id ?? 'default'}
        onClose={() => setSelectedNode(null)}
        onAskAbout={(q) => runQuery(q)}
      />
    </div>
  )
}
