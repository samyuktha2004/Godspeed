export type ErrorCode =
  | 'NETWORK_ERROR'
  | 'AUTH_ERROR'
  | 'RBAC_ERROR'
  | 'QUERY_TIMEOUT'
  | 'SSE_ERROR'
  | 'WS_ERROR'
  | 'HALLUCINATION'
  | 'NO_RESULTS'
  | 'UNKNOWN'

export interface AppError {
  code:     ErrorCode
  message:  string
  retry?:   boolean
}
