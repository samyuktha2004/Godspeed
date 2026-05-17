export type SignalType = 'query_spike' | 'query_drop' | 'escalation_trend' | 'staleness' | 'dependency_risk'
export type Severity   = 'critical' | 'high' | 'medium' | 'low'

export interface AnomalySignal {
  id:          string
  team_id:     string | null
  signal_type: SignalType
  entity_type: string | null
  entity_id:   string | null
  severity:    Severity
  score:       number
  details:     Record<string, unknown>
  resolved:    boolean
  resolved_by: string | null
  resolved_at: string | null
  detected_at: string
}

export interface SignalsSummary {
  total:       number
  by_type:     Partial<Record<SignalType, number>>
  by_severity: Partial<Record<Severity, number>>
}

export interface HourlyPoint {
  hour:             string
  count:            number
  escalations:      number
  anomaly_score:    number | null
  anomaly_type:     SignalType | null
  anomaly_severity: Severity | null
}

export interface QueryPatternsResponse {
  team_id: string
  hourly:  HourlyPoint[]
}

export interface StalenessDetails {
  title:          string
  age_days:       number
  age_factor:     number
  query_pressure: number
  updated_at:     string
}

export interface StalenessDoc {
  entity_id:   string
  score:       number
  details:     StalenessDetails
  detected_at: string
}

export interface StalenessResponse {
  documents: StalenessDoc[]
  total:     number
}

export interface LibraryRiskDetails {
  library_name:          string
  current_version:       string
  latest_version:        string
  version_lag:           number
  downstream_count:      number
  downstream_normalized: number
  incident_count:        number
  incident_rate:         number
  poisson_30d:           number
}

export interface LibraryRisk {
  entity_id:   string
  score:       number
  details:     LibraryRiskDetails
  detected_at: string
}

export interface DependencyRiskResponse {
  libraries: LibraryRisk[]
  total:     number
}

export interface SignalsResponse {
  signals: AnomalySignal[]
  total:   number
}
