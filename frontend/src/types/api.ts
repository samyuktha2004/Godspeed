export interface QueryInput {
  query:      string
  team_id:    string
  session_id: string
}

export interface AgentTask {
  agent:      'doc_search' | 'ticket_lookup' | 'confluence_search' | 'slack_search' | 'live_docs' | 'summariser' | 'sql_query'
  input:      string
  depends_on: string[]
}

export interface ExecutionPlan {
  tasks:     AgentTask[]
  reasoning: string
}

export interface RetrievedChunk {
  chunk_id:       string
  text:           string
  source:         string
  source_type:    string
  score:          number
  reranker_score?: number
}

export interface AgentResult {
  agent:                string
  chunks:               RetrievedChunk[]
  retrieval_confidence: 'high' | 'medium' | 'low'
  error?:               string
}

export interface GuardrailResult {
  score:    number
  escalate: boolean
}

// SSE event payloads keyed by event name
export interface SSEEventMap {
  plan_ready:        ExecutionPlan
  agent_started:     { agent: string }
  agent_done:        { agent: string; retrieval_confidence: 'high' | 'medium' | 'low'; error?: string }
  synthesis_started: Record<string, never>
  answer_chunk:      { chunk: string }
  citations:         { chunks: RetrievedChunk[] }
  guardrail_result:  GuardrailResult
  done:              Record<string, never>
  error:             { message: string }
}

export type SSEEventName = keyof SSEEventMap

// Graph streaming types
export interface GraphNode {
  id:    string
  label: 'Service' | 'Library' | 'Incident' | 'Team'
  name:  string
}

export interface GraphEdge {
  from: string
  to:   string
  rel:  'DEPENDS_ON' | 'CAUSED_BY' | 'OWNED_BY' | 'MENTIONS' | 'REFERENCES' | 'HAS_CHUNK' | 'DOCUMENTS'
}

export interface GraphDoneEvent {
  nodes: number
  edges: number
}

// REST response shapes
export interface GraphNodesResponse {
  count: number
  nodes: Array<{ label: string; name: string }>
}

export interface GraphTraverseResponse {
  type:    string
  name:    string
  team_id: string
  chunks:  string[]
}

export interface FeedbackRequest {
  sentiment: 'helpful' | 'not_helpful' | 'hallucinated'
  text?:     string
}
