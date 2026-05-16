# 03 · Analytics, Query Intelligence & Planned Extensions (Areas 3–5)

> **Document purpose:** Full specification for Area 3 (Analytics & NL Query Intelligence) and the planned extension specs for Area 4 (Anomaly Detection & Forecasting) and Area 5 (Knowledge Graph Extraction). Every Area 3 component is designed as a direct feedback loop into Areas 1 and 2.

---

## Table of Contents

1. [Area 3 Overview — The Feedback Loop Principle](#1-area-3-overview--the-feedback-loop-principle)
2. [Query Classification & Routing](#2-query-classification--routing)
3. [Query Intelligence Layer (Feeds Area 1)](#3-query-intelligence-layer-feeds-area-1)
4. [Natural Language Analytics Interface](#4-natural-language-analytics-interface)
5. [Knowledge Health Dashboard (Powered by Area 2)](#5-knowledge-health-dashboard-powered-by-area-2)
6. [Proactive Intelligence Agent](#6-proactive-intelligence-agent)
7. [Cross-Team Silo Detector](#7-cross-team-silo-detector)
8. [Role-Based Analytics Views](#8-role-based-analytics-views)
9. [Area 4 — Anomaly Detection & Forecasting (Planned)](#9-area-4--anomaly-detection--forecasting-planned)
10. [Area 5 — Knowledge Graph Extraction (Planned)](#10-area-5--knowledge-graph-extraction-planned)
11. [Five-Area Interaction Map](#11-five-area-interaction-map)
12. [Interaction Log Schema](#12-interaction-log-schema)

---

## 1. Area 3 Overview — The Feedback Loop Principle

Area 3 is **not** a standalone dashboard bolted on top of the system. Every component is designed as a direct feedback loop into Areas 1 and 2.

```
Area 3 feeds Area 1:
    Query analytics → retrieval ranking weight updates (nightly)
    Spike detection → pre-trigger T3 live fetch
    Frequently retrieved docs → boost in T1 ranking

Area 3 feeds Area 2:
    Gap signals → surfaced to managers for ingestion priority
    Silo detection signals → cross-team access decisions
    Escalation patterns → knowledge loop enrichment targets

Area 2 feeds Area 3:
    Critic Agent validation events → health dashboard metrics
    GLiNER PII flags → compliance risk panel
    Escalation events → HITL queue dashboard
    Knowledge loop tickets → gap closure tracking

Area 1 feeds Area 3:
    Retrieval layer distribution (T1 vs T2 vs T3) → system health
    T3 usage patterns → candidate topics for T1 enrichment
```

**The analytics layer makes Areas 1 and 2 progressively smarter every week without manual intervention.**

---

## 2. Query Classification & Routing

Every query entering the Orchestrator is classified into one of five types before routing.

### Query Types

| Type | Routing Target | Retrieval Strategy | Example |
|---|---|---|---|
| `lookup` | Doc Search Agent → T1 (Page Index priority) | Dense + BM25 for precise document location | "What is the SLA for the payments service?" |
| `summarisation` | Summariser Agent → T1 + Page Index | Page-hierarchy-aware retrieval | "Summarise the onboarding runbook for backend engineers" |
| `troubleshooting` | Live Doc Agent → T3 + T1 + Jira Ticket Agent | All three retrieval layers in parallel | "Why is my Kubernetes ingress failing after v1.30 upgrade?" |
| `comparison` | Doc Search Agent → T1 multi-document | Multi-doc dense retrieval, cross-doc context | "Differences between our v2 and v3 API authentication?" |
| `analytics` | Analytics Agent → Query Log DB | NL-to-SQL translation | "Which docs did the infra team access most this month?" |

### Classification Implementation

```python
# src/agents/orchestrator.py

QUERY_CLASSIFIER_PROMPT = """
Classify this query into exactly one type:
- lookup: seeking a specific fact, definition, or policy
- summarisation: requesting a summary of a document or topic
- troubleshooting: debugging an error, understanding why something broke
- comparison: comparing two or more options, versions, or approaches
- analytics: asking about usage patterns, team activity, or system metrics

Query: {query}

Return JSON: {{"type": "lookup|summarisation|troubleshooting|comparison|analytics", "confidence": 0.0-1.0}}
"""

async def classify_and_route(query: str, user: User) -> AgentRoute:
    classification = await llm_haiku.classify(
        QUERY_CLASSIFIER_PROMPT.format(query=query)
    )
    
    # Log classification event immediately (feeds Area 3)
    await interaction_log.record(QueryEvent(
        query_text=query,
        query_type=classification.type,
        user_id=user.id,
        team_id=user.team_id,
        timestamp=datetime.utcnow(),
        rbac_context=user.access_level
    ))
    
    return route_to_agent(classification.type, query, user)
```

---

## 3. Query Intelligence Layer (Feeds Area 1)

### Interaction Log

Every query event is logged with full context. This log is the raw material for Area 1 improvement.

```sql
-- Schema: src/db/migrations/003_interaction_log.sql

CREATE TABLE query_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_text      TEXT NOT NULL,
    query_type      VARCHAR(20) NOT NULL,  -- lookup|summarisation|troubleshooting|comparison|analytics
    user_id         UUID NOT NULL,
    team_id         UUID NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Retrieval context
    retrieval_layer VARCHAR(10),           -- t1|t2|t3|combined
    chunks_retrieved INTEGER,
    reranking_score FLOAT,
    
    -- Validation context
    generator_confidence    FLOAT,
    critic_verdict          VARCHAR(20),  -- pass|fail|escalate
    critic_confidence       FLOAT,
    escalation_reason       TEXT,
    
    -- Outcome
    answer_delivered        BOOLEAN,
    ticket_created          UUID,          -- FK to knowledge_loop_tickets
    
    -- Topic context (populated by nightly clustering job)
    topic_cluster           VARCHAR(100),
    topic_embedding         vector(1024)   -- pgvector for semantic clustering
);

CREATE INDEX idx_query_events_team_timestamp ON query_events(team_id, timestamp DESC);
CREATE INDEX idx_query_events_topic_cluster ON query_events(topic_cluster);
CREATE INDEX idx_query_events_critic_verdict ON query_events(critic_verdict);
```

### Retrieval Feedback Loop (Area 3 → Area 1)

```python
# src/analytics/retrieval_feedback.py
# Runs nightly as a scheduled job

async def update_retrieval_weights():
    """
    Update T1 retrieval ranking weights based on query interaction patterns.
    """
    
    # 1. Identify high-frequency topic clusters (last 7 days)
    frequent_topics = await db.query("""
        SELECT topic_cluster, COUNT(*) as query_count, 
               AVG(critic_confidence) as avg_confidence
        FROM query_events
        WHERE timestamp > NOW() - INTERVAL '7 days'
        GROUP BY topic_cluster
        ORDER BY query_count DESC
        LIMIT 50
    """)
    
    # 2. Boost retrieval rank for documents in high-frequency, high-confidence clusters
    for topic in frequent_topics:
        if topic.avg_confidence > 0.85:  # High confidence = good retrieval
            await qdrant_client.update_payload_batch(
                collection_name="enterprise_kb",
                filter=PayloadFilter(topic_cluster=topic.topic_cluster),
                payload_update={"retrieval_boost": topic.query_count * 0.01}
            )
    
    # 3. Flag T3-resolved queries for T1 enrichment
    t3_candidates = await db.query("""
        SELECT DISTINCT topic_cluster, COUNT(*) as t3_count
        FROM query_events
        WHERE retrieval_layer = 't3'
          AND critic_verdict = 'pass'
          AND timestamp > NOW() - INTERVAL '7 days'
        GROUP BY topic_cluster
        HAVING COUNT(*) >= 3  -- Queried via T3 3+ times → candidate for T1 indexing
    """)
    
    for candidate in t3_candidates:
        await enrichment_queue.add(T1EnrichmentTask(
            topic_cluster=candidate.topic_cluster,
            priority="high",
            reason="Repeated T3 resolution — promotes to T1 index"
        ))
    
    # 4. Emit gap signals for low-confidence clusters
    low_confidence_clusters = await db.query("""
        SELECT topic_cluster, AVG(critic_confidence) as avg_conf, COUNT(*) as count
        FROM query_events
        WHERE timestamp > NOW() - INTERVAL '7 days'
          AND critic_verdict IN ('fail', 'escalate')
        GROUP BY topic_cluster
        HAVING COUNT(*) >= 2
    """)
    
    for cluster in low_confidence_clusters:
        await gap_signal_db.upsert(GapSignal(
            topic_cluster=cluster.topic_cluster,
            severity="high" if cluster.avg_conf < 0.4 else "medium",
            evidence_count=cluster.count,
            detected_at=datetime.utcnow()
        ))
```

---

## 4. Natural Language Analytics Interface

Managers and heads ask in plain language. The Analytics Agent translates to structured queries.

### Example Queries and What They Hit

| Natural Language Query | Role | Query Type | Source Table |
|---|---|---|---|
| "Which documents did my team access most this month?" | Manager | Aggregation | `query_events` JOIN `chunks_retrieved` |
| "What questions couldn't the system answer last week?" | Manager/Head | Filter | `query_events WHERE critic_verdict = 'escalate'` |
| "Show me knowledge gaps in the infrastructure team" | Manager | Filter + JOIN | `gap_signals` JOIN `query_events` |
| "Which teams are searching for the same things?" | Head | Overlap analysis | `query_events` clustered by `topic_embedding` |
| "What is our hallucination rate this sprint?" | Head | Rate calculation | `query_events` where `critic_verdict = 'fail'` |
| "Which open-source libraries have we had most questions about?" | Any | Topic frequency | `query_events WHERE query_type = 'troubleshooting'` |

### Analytics Agent Implementation

```python
# src/agents/analytics_agent.py

NL_TO_SQL_PROMPT = """
You are an analytics agent with access to an enterprise knowledge system's interaction database.

Available tables:
- query_events: (id, query_text, query_type, user_id, team_id, timestamp, 
                 retrieval_layer, critic_verdict, critic_confidence, topic_cluster)
- gap_signals: (id, topic_cluster, severity, evidence_count, detected_at, resolved_at)
- knowledge_loop_tickets: (id, query, fix, confidence, team_id, timestamp, topic_cluster)
- team_members: (user_id, team_id, role)
- silo_events: (id, team_a_id, team_b_id, topic_cluster, overlap_count, detected_at)

Current user: team_id={team_id}, role={role}
RBAC constraint: Only return data for teams the user has access to.

Translate this question to a SQL query:
{question}

Return JSON: {{"sql": "SELECT ...", "explanation": "This query..."}}
IMPORTANT: Always include WHERE team_id IN ({accessible_teams}) for data access control.
"""

async def handle_analytics_query(question: str, user: User) -> AnalyticsResult:
    # Determine accessible teams based on RBAC
    if user.role == "head":
        accessible_teams = await db.get_all_team_ids()
    elif user.role == "manager":
        accessible_teams = [user.team_id] + await db.get_report_team_ids(user.team_id)
    else:
        accessible_teams = [user.team_id]
    
    # Generate SQL
    sql_response = await llm_sonnet.generate(
        NL_TO_SQL_PROMPT.format(
            team_id=user.team_id,
            role=user.role,
            question=question,
            accessible_teams=','.join([f"'{t}'" for t in accessible_teams])
        )
    )
    
    # Execute with parameterised query (SQL injection prevention)
    results = await db.execute_safe(sql_response['sql'])
    
    # Format results as cited analytics response
    return AnalyticsResult(
        data=results,
        explanation=sql_response['explanation'],
        generated_sql=sql_response['sql'],  # Shown to head/admin users for auditability
        timestamp=datetime.utcnow()
    )
```

---

## 5. Knowledge Health Dashboard (Powered by Area 2)

The dashboard is built entirely on events emitted by the Area 2 validation pipeline. No separate data collection required.

### Dashboard Metrics

| Metric | Source Event (Area 2) | Update Frequency | Visible To |
|---|---|---|---|
| Hallucination Rate (%) | Critic Agent `verdict = 'fail'` events / total | Real-time | Managers, Heads |
| Knowledge Gap Heatmap | `gap_signals` table (low-confidence + escalations by topic) | Nightly | Managers, Heads |
| Coverage Score by Team | % queries answered without escalation per team | Nightly | Managers |
| Top Escalated Topics | `query_events WHERE critic_verdict = 'escalate'` clustered | Real-time | Managers |
| PII Risk Events | GLiNER flag events from ingestion pipeline | Real-time | Compliance, Heads |
| Retrieval Layer Distribution | T1 vs T2 vs T3 usage per team | Nightly | Admin, Heads |
| Knowledge Loop Velocity | New tickets added to KB per day | Daily | Heads |
| Silo Overlap Score | `silo_events` count by team pair | Nightly | Heads |

### Dashboard API Endpoints

```python
# src/api/dashboard.py

@router.get("/dashboard/health/{team_id}")
async def team_health(team_id: str, user: User = Depends(get_current_user)):
    require_manager_access(user, team_id)
    
    return {
        "hallucination_rate": await metrics.hallucination_rate(team_id, days=7),
        "gap_heatmap": await metrics.gap_heatmap(team_id),
        "coverage_score": await metrics.coverage_score(team_id, days=7),
        "top_escalated_topics": await metrics.top_escalations(team_id, limit=10),
        "retrieval_distribution": await metrics.retrieval_distribution(team_id, days=7),
        "knowledge_loop_velocity": await metrics.loop_velocity(team_id, days=7),
    }

@router.get("/dashboard/org")
async def org_health(user: User = Depends(get_current_user)):
    require_head_access(user)
    
    return {
        "all_teams": await metrics.all_team_summaries(),
        "silo_map": await metrics.silo_detection_map(),
        "org_hallucination_rate": await metrics.hallucination_rate(org_wide=True, days=7),
        "pii_risk_events": await metrics.pii_events(days=7),
        "system_health": await metrics.system_health(),
    }
```

---

## 6. Proactive Intelligence Agent

Pushes relevant knowledge to users before they need to search.

### Trigger Conditions and Actions

| Trigger | Data Source | Action | Recipient |
|---|---|---|---|
| Dependency Tracker detects deprecation in a library a team uses frequently | Dep Tracker + `query_events` topic frequency | Push: "Your service uses Library X. Breaking change in v4.2. View impact report." | Relevant team members |
| `gap_signals` table: 5+ queries on topic with low confidence in 7 days | Area 2 gap signals | Push to Manager: "Knowledge gap detected: 7 queries about Kafka config this week had low confidence." | Team Manager |
| New PR merged to monitored repo | GitHub webhook | Nightly CAG update: summarise and inject into team context | No push — silent update |
| Silo detected: two teams querying same topic cluster | `silo_events` table | Push to Head: "Teams X and Y are both searching for Kubernetes RBAC config. Consider enabling cross-team visibility." | Company Head |
| Escalation rate spikes above 3x baseline for a team | `query_events` control chart | Push to Manager: "Escalation rate for Infra team is 3x normal this week. 5 open escalations." | Team Manager |
| T3 usage 3+ times on same topic → T1 enrichment candidate | `query_events WHERE retrieval_layer = 't3'` | Push to Admin: "Topic 'FastAPI rate limiting' queried via live fetch 3 times. Recommend adding to knowledge base." | System Admin |

### Implementation

```python
# src/agents/proactive_agent.py
# Runs on: event-triggered + nightly sweep

class ProactiveAgent:
    
    async def check_dependency_alerts(self):
        """Triggered by Dependency Tracker on new breaking change detection"""
        new_changes = await dep_tracker.get_unnotified_changes()
        
        for change in new_changes:
            # Find teams that frequently query this library
            affected_teams = await db.query("""
                SELECT team_id, COUNT(*) as query_count
                FROM query_events
                WHERE topic_cluster ILIKE %s
                  AND timestamp > NOW() - INTERVAL '30 days'
                GROUP BY team_id
                HAVING COUNT(*) >= 2
            """, (f"%{change.library}%",))
            
            for team in affected_teams:
                await notification_service.push(
                    team_id=team.team_id,
                    title=f"⚠️ Breaking change in {change.library}",
                    body=f"Your team has {team.query_count} recent queries about {change.library}. "
                         f"Version {change.new_version} introduces: {change.summary}. "
                         f"Impact report available.",
                    link=f"/dependency-tracker/impact/{change.id}",
                    priority="high"
                )
    
    async def check_gap_alerts(self):
        """Nightly sweep of gap signals"""
        new_gaps = await gap_signal_db.get_unnotified(min_evidence=5)
        
        for gap in new_gaps:
            manager = await db.get_team_manager(gap.team_id)
            await notification_service.push(
                user_id=manager.id,
                title=f"📚 Knowledge gap detected: {gap.topic_cluster}",
                body=f"{gap.evidence_count} queries about '{gap.topic_cluster}' "
                     f"had low confidence this week. Consider adding documentation.",
                priority="medium"
            )
```

---

## 7. Cross-Team Silo Detector

### How It Works

```python
# src/analytics/silo_detector.py
# Runs nightly

async def detect_silos():
    """
    Identify teams querying the same semantic topics without cross-team access.
    Uses topic_embedding column for semantic similarity, not just keyword matching.
    """
    
    # 1. Get topic cluster centroids per team (last 30 days)
    team_topics = await db.query("""
        SELECT team_id, topic_cluster, topic_embedding,
               COUNT(*) as query_count,
               AVG(critic_confidence) as avg_confidence
        FROM query_events
        WHERE timestamp > NOW() - INTERVAL '30 days'
          AND critic_verdict != 'escalate'
        GROUP BY team_id, topic_cluster, topic_embedding
        HAVING COUNT(*) >= 3
    """)
    
    # 2. Compute pairwise semantic similarity between team topic profiles
    team_pairs = combinations(team_topics_by_team.keys(), 2)
    
    for team_a, team_b in team_pairs:
        # Skip if teams already have cross-access configured
        if await rbac.has_cross_team_access(team_a, team_b):
            continue
        
        # Compute topic overlap via cosine similarity on embeddings
        overlap_topics = []
        for topic_a in team_topics_by_team[team_a]:
            for topic_b in team_topics_by_team[team_b]:
                similarity = cosine_similarity(
                    topic_a.topic_embedding, 
                    topic_b.topic_embedding
                )
                if similarity > 0.85:  # Semantic overlap threshold
                    overlap_topics.append({
                        "topic": topic_a.topic_cluster,
                        "team_a_count": topic_a.query_count,
                        "team_b_count": topic_b.query_count,
                        "similarity": similarity
                    })
        
        if overlap_topics:
            total_duplicated_queries = sum(
                t['team_a_count'] + t['team_b_count'] for t in overlap_topics
            )
            # Estimate: avg 20min per query * duplicated queries
            duplicated_hours = total_duplicated_queries * 20 / 60
            
            await silo_events.upsert(SiloEvent(
                team_a_id=team_a,
                team_b_id=team_b,
                overlap_topics=overlap_topics,
                overlap_count=len(overlap_topics),
                estimated_duplicated_hours=duplicated_hours,
                detected_at=datetime.utcnow()
            ))
```

---

## 8. Role-Based Analytics Views

```python
# Access control for analytics — enforced at API layer, not UI layer

ANALYTICS_PERMISSIONS = {
    "new_employee": [
        "own_query_history",
        "onboarding_progress"
    ],
    "employee": [
        "own_query_history",
        "team_frequently_accessed_docs",  # Anonymised
    ],
    "manager": [
        "team_health_dashboard",
        "team_gap_heatmap",
        "team_search_insights",           # Anonymised by user
        "team_escalation_queue",
        "team_silo_alerts",
        "hitl_approval_queue",
        "rbac_management",
    ],
    "head": [
        "*all_manager_permissions",
        "org_wide_health_dashboard",
        "cross_team_silo_map",
        "org_hallucination_rate",
        "pii_risk_events",
        "system_health_metrics",
        "all_team_gap_analysis",
        "org_rbac_management",
    ]
}
```

---

## 9. Area 4 — Anomaly Detection & Forecasting

> **Status: Implemented** on branch `anomaly-and-forecasting`. See [`anomaly-and-forecasting/`](./anomaly-and-forecasting/README.md) for full implementation docs.  
> The specs below describe the original design intent. The actual implementation uses plain PostgreSQL (no InfluxDB) and stdlib-only algorithms (no external ML dependencies).

### Component 1 — Query Spike Detector

```python
# Input: query_events table (Area 3 interaction log)
# Method: Z-score anomaly on rolling 15-minute and 1-hour windows per topic cluster

async def detect_query_spikes():
    for topic_cluster in active_clusters:
        # Get rolling window counts
        recent_counts = await db.query("""
            SELECT date_trunc('minute', timestamp) as minute,
                   COUNT(*) as query_count
            FROM query_events
            WHERE topic_cluster = %s
              AND timestamp > NOW() - INTERVAL '2 hours'
            GROUP BY minute
            ORDER BY minute
        """, (topic_cluster,))
        
        # Compute baseline (30-day rolling average for this cluster at this time of day)
        baseline = await metrics.get_baseline(topic_cluster, time_of_day=current_hour)
        
        # Z-score anomaly detection
        z_score = (current_15min_count - baseline.mean) / baseline.std
        
        if z_score > 3.0:  # 3-sigma threshold
            # Pre-trigger T3 live fetch for this topic
            await live_doc_agent.prefetch(topic_cluster)
            
            # Notify team manager
            await proactive_agent.spike_alert(topic_cluster, z_score)
```

### Component 2 — Knowledge Staleness Forecasting

```python
# Input: document ingest timestamps (Area 2) + library release cadence (Dep Tracker)
# Output: Staleness Risk Score (0-100) per indexed document

async def compute_staleness_scores():
    docs = await db.query("""
        SELECT d.id, d.source_uri, d.source_type, d.ingested_at, 
               d.content_hash, d.library_name,
               COUNT(qe.id) as query_frequency
        FROM indexed_documents d
        LEFT JOIN query_events qe ON qe.source_uri = d.source_uri
          AND qe.timestamp > NOW() - INTERVAL '30 days'
        GROUP BY d.id
    """)
    
    for doc in docs:
        days_since_ingest = (datetime.utcnow() - doc.ingested_at).days
        
        # Get library release cadence (from Dependency Tracker)
        if doc.library_name:
            release_cadence = await dep_tracker.get_release_cadence(doc.library_name)
            # Expected update frequency based on historical releases
            expected_update_days = release_cadence.median_days_between_releases
        else:
            expected_update_days = 90  # Default for non-library docs
        
        # Staleness score formula:
        # Higher query frequency → higher priority even if not stale yet
        base_staleness = min(100, (days_since_ingest / expected_update_days) * 100)
        frequency_weight = min(2.0, 1 + (doc.query_frequency / 10))
        
        staleness_score = min(100, base_staleness * frequency_weight)
        
        await doc_metadata.update(doc.id, staleness_score=staleness_score)
```

### Component 3 — Escalation Rate Anomaly Detection

```python
# Input: query_events WHERE critic_verdict = 'escalate' (Area 2)
# Method: Control chart (3-sigma) on per-team escalation rate

async def detect_escalation_anomalies():
    for team_id in active_teams:
        # Get 30-day baseline
        baseline = await metrics.escalation_baseline(team_id, days=30)
        
        # Get current 7-day rate
        current_rate = await metrics.escalation_rate(team_id, days=7)
        
        # Upper control limit = mean + 3*std
        ucl = baseline.mean + (3 * baseline.std)
        
        if current_rate > ucl:
            severity = "critical" if current_rate > (ucl * 2) else "warning"
            
            await gap_signal_db.upsert(GapSignal(
                team_id=team_id,
                signal_type="escalation_spike",
                severity=severity,
                current_rate=current_rate,
                baseline_rate=baseline.mean,
                ucl=ucl
            ))
```

### Component 4 — Dependency Risk Forecasting

```python
# Input: Dependency Tracker version snapshot history (Area 2)
# Model: Poisson process on breaking change frequency per library

async def compute_dependency_risk_scores():
    for library in monitored_libraries:
        history = await dep_tracker.get_change_history(library)
        
        # Compute breaking change rate (changes per day)
        breaking_changes = [h for h in history if h.change_type in 
                           ['deprecated', 'removed', 'signature_changed']]
        
        if len(breaking_changes) < 2:
            risk_score = 0.1  # Insufficient history
            continue
        
        # Poisson parameter: average breaking changes per 30 days
        total_days = (history[-1].date - history[0].date).days
        lambda_30 = (len(breaking_changes) / total_days) * 30
        
        # Days since last breaking change
        days_since_last = (datetime.utcnow() - breaking_changes[-1].date).days
        
        # Internal usage weight from query frequency
        usage_weight = await metrics.library_query_frequency(library, days=30)
        
        # Risk score = Poisson probability × usage weight × recency factor
        probability_of_change_in_30d = 1 - math.exp(-lambda_30)
        recency_factor = min(2.0, days_since_last / 30)  # Longer since last = higher risk
        
        risk_score = probability_of_change_in_30d * usage_weight * recency_factor
        
        await dep_tracker.update_risk_score(library, risk_score=min(100, risk_score * 100))
```

---

## 10. Area 5 — Knowledge Graph Extraction (Planned)

> **Status: Planned Extension.** Requires: Neo4j (or NetworkX for small deployments). GLiNER entity extraction already runs at ingest (Area 2) — Area 5 adds the relation extraction step on top.

### Component 1 — Entity-Relation Extraction at Ingest

```python
# Extension to Stage 3 of the ingestion pipeline
# After GLiNER extracts entities, add relation classification

RELATION_TYPES = [
    ("USES", "Service/function X uses library/API Y"),
    ("OWNS", "Team A owns service/doc X"),
    ("REPLACED_BY", "API X is replaced by API Y"),
    ("DEPENDS_ON", "Service X depends on service Y"),
    ("DOCUMENTS", "Document X describes service Y"),
    ("AUTHORED_BY", "Document X was written by person Y — only if PII-safe"),
]

async def extract_relations(
    text: str, 
    entities: list[Entity]
) -> list[Relation]:
    # Use LLM to extract typed relations between co-occurring entities
    prompt = f"""
    Given these entities extracted from a document: {[e.text for e in entities]}
    
    And this text: {text[:2000]}  # First 2000 chars for context
    
    Extract relationships between entities. Only include relationships 
    explicitly stated or strongly implied by the text.
    
    Return JSON array:
    [{{"subject": "entity1", "relation": "USES|OWNS|DEPENDS_ON|etc", 
       "object": "entity2", "confidence": 0.0-1.0}}]
    """
    
    relations = await llm_haiku.structured_output(prompt, schema=list[Relation])
    return [r for r in relations if r.confidence > 0.7]
```

### Component 2 — API Dependency Graph

```python
# Materialises Dependency Tracker's implicit impact scan as a queryable graph
# neo4j_client: src/graph/neo4j_client.py

async def build_api_dependency_graph(impact_scan_result: ImpactScanResult):
    """
    Called by Dependency Tracker after each impact scan.
    Incrementally updates the graph — no full rebuild needed.
    """
    
    for affected_file in impact_scan_result.affected_files:
        # Node: internal file
        await neo4j.merge_node("File", {
            "path": affected_file.path,
            "service": affected_file.service_name,
            "team_id": affected_file.team_id
        })
        
        # Node: external library symbol
        await neo4j.merge_node("LibrarySymbol", {
            "library": impact_scan_result.library,
            "symbol": impact_scan_result.affected_symbol,
            "version_constraint": affected_file.version_constraint
        })
        
        # Edge: IMPORTS
        await neo4j.merge_relationship(
            from_node=("File", {"path": affected_file.path}),
            to_node=("LibrarySymbol", {"symbol": impact_scan_result.affected_symbol}),
            rel_type="IMPORTS",
            properties={"line_number": affected_file.line_number}
        )

# Example graph traversal query:
# "What internal services would be affected if Library X drops Python 3.9 support?"
CYPHER_IMPACT_QUERY = """
MATCH (lib:LibrarySymbol {library: $library_name})
      <-[:IMPORTS]-(file:File)
      <-[:CONTAINS]-(service:Service)
      <-[:OWNS]-(team:Team)
WHERE file.python_version_constraint CONTAINS '3.9'
RETURN service.name, team.name, collect(file.path) as affected_files
ORDER BY service.name
"""
```

### Component 3 — Knowledge Provenance Graph

```python
# Full audit trail as a traversable graph
# Critical for GDPR/DPDP compliance and answer invalidation on doc updates

PROVENANCE_CYPHER_QUERIES = {
    
    # Compliance query: which users received answers citing Document X?
    "users_who_received_answers_from_doc": """
        MATCH (doc:Document {uri: $source_uri})
              <-[:CITED_IN]-(chunk:Chunk)
              <-[:DERIVED_FROM]-(answer:Answer)
              <-[:RECEIVED]-(user:User)
        RETURN user.id, user.team_id, answer.timestamp, answer.text
        ORDER BY answer.timestamp DESC
    """,
    
    # Impact query: which answers might be wrong after doc update?
    "answers_to_invalidate_after_doc_update": """
        MATCH (doc:Document {uri: $source_uri})
              <-[:CITED_IN]-(chunk:Chunk)
              <-[:DERIVED_FROM]-(answer:Answer)
        WHERE answer.timestamp < $doc_updated_at
          AND answer.critic_confidence > 0.7  -- Only high-confidence answers
        RETURN answer.id, answer.text, answer.timestamp
        ORDER BY answer.timestamp DESC
    """,
    
    # Chain query: full provenance for an answer
    "full_provenance_chain": """
        MATCH path = (answer:Answer {id: $answer_id})
                     -[:DERIVED_FROM*]->(chunk:Chunk)
                     -[:CITED_IN]->(doc:Document)
        RETURN path
    """
}
```

### Component 4 — Team-Concept Ownership Graph

```python
# Powers Silo Detector with graph traversal instead of statistical overlap
# Also enables expert identification for escalation routing

# Build graph from RBAC + query interaction data
async def build_ownership_graph():
    
    # Team → Document ownership (from RBAC)
    teams_docs = await rbac.get_all_team_document_access()
    for team_id, doc_uris in teams_docs.items():
        for uri in doc_uris:
            await neo4j.merge_relationship(
                from_node=("Team", {"id": team_id}),
                to_node=("Document", {"uri": uri}),
                rel_type="OWNS"
            )
    
    # Team → Topic cluster (from query interaction log)
    team_topics = await db.query("""
        SELECT team_id, topic_cluster, COUNT(*) as query_count
        FROM query_events WHERE timestamp > NOW() - INTERVAL '90 days'
        GROUP BY team_id, topic_cluster HAVING COUNT(*) >= 3
    """)
    for row in team_topics:
        await neo4j.merge_relationship(
            from_node=("Team", {"id": row.team_id}),
            to_node=("TopicCluster", {"name": row.topic_cluster}),
            rel_type="QUERIES",
            properties={"query_count": row.query_count}
        )

# Expert identification query (escalation routing when RAG fails)
EXPERT_QUERY = """
MATCH (person:Person)-[:MEMBER_OF]->(team:Team)
      -[:QUERIES]->(topic:TopicCluster {name: $topic})
WHERE team.id IN $accessible_teams
RETURN person.id, person.name, team.name,
       sum([(team)-[q:QUERIES]->(topic) | q.query_count]) as topic_expertise
ORDER BY topic_expertise DESC
LIMIT 3
"""
```

---

## 11. Five-Area Interaction Map

| Area | Consumes From | Produces | Feeds Back To |
|---|---|---|---|
| **Area 1 — Hybrid RAG** | Area 3: ranking weight updates; Area 5: graph traversal context | Retrieved chunks + confidence; Live-fetched external docs | Area 2: raw chunks for validation; Area 3: retrieval layer logs |
| **Area 2 — Pipelines & Validation** | Area 1: retrieved chunks for Critic; Area 3: interaction event triggers | Validated answers + escalations; Knowledge loop tickets; GLiNER entity extractions | Area 3: validation events for dashboards; Area 5: entity extractions for graph |
| **Area 3 — Analytics & NL Intel** | Area 1: retrieval layer logs; Area 2: validation + escalation events | Query event log (time series); Gap signals + silo detections; Proactive alerts | Area 1: ranking weight updates; Area 4: anomaly input streams; Area 5: team-query edges |
| **Area 4 — Anomaly & Forecast** | Area 3: query event time series; Area 2: critic escalation logs; Dep Tracker: release history | Spike alerts; Staleness forecasts; Dep risk scores; Escalation anomalies | Area 1: pre-trigger T3 fetch on spike; Area 3: anomaly alerts to dashboards |
| **Area 5 — Knowledge Graph** | Area 2: GLiNER entity extractions; Dep Tracker: implicit dep graph; Area 3: team-query ownership edges | Typed entity-relation graph; Provenance audit graph; API dependency traversal | Area 1: graph context injected into RAG; Area 2: provenance-based re-validation; Area 3: graph-precise silo detection |

---

## 12. Interaction Log Schema

Complete schema for the interaction log database — the backbone of Areas 3, 4, and 5.

```sql
-- Full schema: src/db/migrations/

-- Core query events
CREATE TABLE query_events ( ... );          -- See Section 3 above

-- Gap signals (from Area 2 + Area 3)
CREATE TABLE gap_signals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id         UUID,
    topic_cluster   VARCHAR(200),
    signal_type     VARCHAR(50),  -- low_confidence|escalation_spike|no_coverage
    severity        VARCHAR(20),  -- low|medium|high|critical
    evidence_count  INTEGER,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at     TIMESTAMPTZ,
    resolution_note TEXT
);

-- Silo detection events
CREATE TABLE silo_events (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_a_id                   UUID NOT NULL,
    team_b_id                   UUID NOT NULL,
    overlap_topics              JSONB,
    overlap_count               INTEGER,
    estimated_duplicated_hours  FLOAT,
    detected_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notified_at                 TIMESTAMPTZ,
    resolved_at                 TIMESTAMPTZ
);

-- Knowledge loop tickets (from Area 2)
CREATE TABLE knowledge_loop_tickets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query           TEXT NOT NULL,
    fix             TEXT NOT NULL,
    source_uris     TEXT[],
    confidence      FLOAT,
    team_id         UUID NOT NULL,
    topic_cluster   VARCHAR(200),
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    qdrant_point_id UUID   -- Reference to vector index entry
);

-- PII risk events (from GLiNER at ingest)
CREATE TABLE pii_risk_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type     VARCHAR(50),
    source_uri      TEXT,
    source_type     VARCHAR(20),
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

*Previous: [02_rag_pipeline_and_validation.md](./02_rag_pipeline_and_validation.md)*
*Next: [04_integrations_and_tech_stack.md](./04_integrations_and_tech_stack.md)*
