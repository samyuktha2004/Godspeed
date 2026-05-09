import { useCallback, useRef, useState } from 'react'
import { useAuthStore } from '@/stores/authStore'
import { useSSEStream } from '@/hooks/useSSEStream'
import { useGraphStream } from '@/hooks/useGraphStream'
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton'
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
import type {
  AgentTask, RetrievedChunk, GuardrailResult, ExecutionPlan,
  GraphNode, GraphEdge,
} from '@/types/api'

export function ResultsPage() {
  const user       = useAuthStore((s) => s.user)
  const sessionRef = useRef(crypto.randomUUID())

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
  const [graphNodes, setGraphNodes]       = useState<GraphNode[]>([])
  const [graphEdges, setGraphEdges]       = useState<GraphEdge[]>([])
  const [hoveredNode, setHoveredNode]     = useState<GraphNode | null>(null)
  const [hoverPos, setHoverPos]           = useState({ x: 0, y: 0 })
  const [selectedNode, setSelectedNode]   = useState<GraphNode | null>(null)
  // Accumulated refs — avoid setState on every 50ms node message
  const nodesAccRef = useRef<GraphNode[]>([])
  const edgesAccRef = useRef<GraphEdge[]>([])

  // ── Hooks ───────────────────────────────────────────────────────────────────
  const { state, error, firstEventArrived, stream } = useSSEStream()
  const { gState, retryCount, firstNodeArrived, connect, disconnect } = useGraphStream()

  // ── Query runner ─────────────────────────────────────────────────────────────
  const runQuery = useCallback(
    async (query: string) => {
      // Reset SSE state
      setPlan([])
      setStatuses({})
      setAnswerText('')
      setCitations([])
      setGuardrail(null)
      setCurrentQuery(query)
      setQueryId(crypto.randomUUID())
      setShareOpen(false)

      // Reset graph state for new query
      nodesAccRef.current = []
      edgesAccRef.current = []
      setGraphNodes([])
      setGraphEdges([])
      setSelectedNode(null)

      // Start fresh WS connection for this query session
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
        onDone: () => {},
        onError: () => {},
      })

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
            setStatuses((prev) => ({
              ...prev,
              [agent]: { agent, state: 'active' },
            }))
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
            setCitations((prev) => [...prev, ...result.chunks])
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
    [stream, connect, disconnect, user],
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

  // ── Derived ─────────────────────────────────────────────────────────────────
  const isLoading   = state === 'loading'
  const isStreaming = state === 'streaming'
  const isComplete  = state === 'complete'
  const isError     = state === 'error'
  const hasData     = firstEventArrived.current
  // Graph panel shows a skeleton when SSE is live but graph hasn't started yet
  const graphLoading = (isLoading || isStreaming) && !firstNodeArrived.current

  return (
    // Wider container to accommodate side-by-side layout on large screens
    <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-4 py-8">
      {/* Search bar — always visible */}
      <SearchBox onSubmit={runQuery} disabled={isLoading || isStreaming} />

      {/* Pre-first-event skeleton */}
      {isLoading && !hasData && <LoadingSkeleton rows={4} />}

      {/* Full error with no partial answer */}
      {isError && !answerText && (
        <TimeoutError
          message={error ?? undefined}
          onRetry={() => currentQuery && runQuery(currentQuery)}
        />
      )}

      {/* Main results: two-column on lg (answer | graph), stacked on mobile */}
      {hasData && (
        <div className="flex flex-col gap-6 lg:grid lg:grid-cols-[1fr_380px] lg:items-start lg:gap-8">

          {/* Left: answer column */}
          <div className="flex flex-col gap-6">
            {plan.length > 0 && (
              <AgentBadges plan={plan} statuses={agentStatuses} />
            )}

            {answerText && <Answer text={answerText} />}

            {guardrail?.escalate && <HallucinationWarning />}

            {isError && answerText && error?.includes('incomplete') && (
              <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
                <span aria-hidden>⚠</span>
                Answer may be incomplete — connection dropped mid-stream.
                <button
                  onClick={() => currentQuery && runQuery(currentQuery)}
                  className="ml-auto shrink-0 underline"
                >
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

            {isComplete && <FollowUp onSubmit={runQuery} />}
          </div>

          {/* Right: graph column (hidden on mobile — KnowledgeGraph has hidden lg:block) */}
          <div className="flex flex-col gap-2">
            <KnowledgeGraph
              nodes={graphNodes}
              edges={graphEdges}
              loading={graphLoading}
              onNodeClick={handleNodeClick}
              onNodeHover={handleNodeHover}
            />
            {gState === 'retrying' && (
              <NetworkRetry attempt={retryCount + 1} />
            )}
          </div>
        </div>
      )}

      {/* Idle home state */}
      {state === 'idle' && !hasData && (
        <div className="flex flex-1 items-center justify-center">
          <p className="text-sm text-stone-400">Ask a question to get started.</p>
        </div>
      )}

      {/* Tooltip — rendered in document root via fixed positioning */}
      <GraphNodeTooltip node={hoveredNode} x={hoverPos.x} y={hoverPos.y} />

      {/* Share modal */}
      <ShareResults query={currentQuery} open={shareOpen} onClose={() => setShareOpen(false)} />

      {/* Detail panel — slide-in on node click */}
      <GraphNodeDetailPanel
        node={selectedNode}
        teamId={user?.team_id ?? 'default'}
        onClose={() => setSelectedNode(null)}
        onAskAbout={(q) => runQuery(q)}
      />
    </div>
  )
}
