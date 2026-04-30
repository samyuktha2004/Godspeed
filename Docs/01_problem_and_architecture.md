# 01 · Problem Statement, Objectives & System Architecture

> **Document purpose:** Defines the exact problem this system solves, the architectural decisions made and why, and how all five focus areas interact as a single product. Read this first before touching any code.

---

## Table of Contents

1. [The Core Problem](#1-the-core-problem)
2. [Problem Dimensions](#2-problem-dimensions)
3. [Objectives](#3-objectives)
4. [Solution Overview](#4-solution-overview)
5. [Three-Area Architecture](#5-three-area-architecture)
6. [Agentic System Design](#6-agentic-system-design)
7. [Full Query Pipeline](#7-full-query-pipeline)
8. [User Roles](#8-user-roles)
9. [Design Principles](#9-design-principles)

---

## 1. The Core Problem

In large IT companies and scaling startups, knowledge is scattered across Confluence, Jira, GitHub repositories, Notion workspaces, PDFs, wiki pages, and open-source documentation sites. No single employee knows where to look. New engineers spend weeks discovering what already exists. Senior engineers keep answering the same questions in support tickets, week after week.

### The Killer Scenario

> A service breaks in production. A deprecated library API changed its call signature three months ago — the announcement was buried in a GitHub changelog. The junior on-call engineer has no idea because the open-source docs changed and nobody connected that to the internal codebase. This happens constantly. It is completely avoidable.

This scenario is not an edge case. It is a systemic failure caused by three simultaneous gaps:

- **Fragmented retrieval** — no unified interface across internal and external knowledge
- **Stale and hallucinated answers** — RAG systems answer from old snapshots and cannot verify their own outputs
- **Invisible intelligence** — no visibility into what teams search for, what fails, and what knowledge is missing

---

## 2. Problem Dimensions

| Problem | Root Cause | Business Cost |
|---|---|---|
| Knowledge silos | Each team's docs live in isolated systems (Notion, Confluence, GitHub) with no cross-team visibility | Repeated work, inconsistent decisions, delayed onboarding |
| Stale documentation | Internal KB lags behind fast-moving open-source libraries | Production incidents from deprecated APIs and breaking changes |
| Hallucinating AI | Even state-of-the-art RAG systems hallucinate 17–33% of the time in specialised domains (Stanford 2025) | Engineers cannot trust AI answers; tool adoption fails |
| PII and compliance risk | All SaaS knowledge tools send enterprise data to external servers | GDPR violations, India DPDP Act non-compliance, data sovereignty loss |
| No live awareness | Systems index once; cannot fetch real-time external documentation | Engineers miss breaking changes until production breaks |
| No knowledge insight | No visibility into what teams search for, what fails, what gaps exist | Repeated escalations, no continuous improvement loop |

---

## 3. Objectives

Four measurable outcomes the system must deliver:

1. **Unify** all enterprise knowledge sources — Notion, Confluence, GitHub, PDFs, URLs, and live external docs — into a single cited answer interface that engineers trust.
2. **Eliminate hallucinations** through adversarial two-agent validation (Generator + Critic), ensuring no ungrounded answer reaches a user.
3. **Surface real-time awareness** of open-source dependency changes via the Dependency Tracker before they cause production incidents.
4. **Generate continuous intelligence** from every query interaction, improving retrieval quality and surfacing actionable knowledge gaps through the Analytics layer.

---

## 4. Solution Overview

**Enterprise Knowledge Copilot** is a fully open-source, locally-compliant, agentic RAG platform that unifies internal and live external knowledge into a single cited, validated answer engine.

The system is structured as **three interdependent focus areas** forming a closed feedback loop:

```
┌─────────────────────────────────────────────────────────────────┐
│                     CLOSED FEEDBACK LOOP                        │
│                                                                 │
│  AREA 1 (RAG)  ──retrieval signal logs──▶  AREA 3 (Analytics)  │
│      ▲                                          │               │
│      │ ranking weight updates                   │ anomaly       │
│      │                                          │ inputs        │
│  AREA 2 (Pipelines)◀──validation events────────▼               │
│      │                              AREA 4 (Anomaly) ──alerts──▶│
│      └──entity extractions──▶  AREA 5 (Graph) ──context──▶ RAG │
└─────────────────────────────────────────────────────────────────┘
```

**Key architectural principle:** The output of Area 1 improves through Area 3 feedback. The output of Area 2 populates Area 3 dashboards. Area 3 proactive intelligence is powered by Area 1 live fetching and Area 2 gap detection. All five areas are one system, not five products.

---

## 5. Three-Area Architecture

### Area 1 — Hybrid RAG System (Core — In Scope)

Three complementary retrieval strategies, each covering gaps the others cannot handle:

| Layer | What It Covers | How |
|---|---|---|
| **T1 — Three-way Hybrid RAG** | Main knowledge base (Notion, Confluence, GitHub, PDFs) | BGE-M3 dense + sparse in one pass + BM25 via RRF fusion → top 50 → BGE-reranker-v2-m3 → top 5 → context compression → LLM |
| **T2 — CAG** | "Just shipped but not yet indexed" gap | Recent sprint summaries, merged PRs, incidents summarised nightly by Haiku → injected into system prompt as team context |
| **T3 — Live Doc Agent** | Real-time external documentation | Firecrawl (JS-rendered docs) + Tavily (web search fallback) → fetch, chunk, embed ephemerally → cite with timestamp |

### Area 2 — Data Pipelines & Validation (Core — In Scope)

- **Ingestion pipeline:** Fetch → Docling clean/parse → GLiNER PII masking (local, zero egress) → semantic chunking → metadata tagging (source, timestamp, RBAC tag, content hash)
- **Generator + Critic Agent:** Two-agent adversarial validation. Answer only reaches user when both agree.
- **Knowledge Loop:** Every resolved query auto-creates a ticket (Query + Fix) → feeds back into RAG pipeline
- **Dependency Tracker:** AST diff + impact scan + auto-patch PR for open-source breaking changes

### Area 3 — Analytics & NL Query Intelligence (Core — In Scope)

- **Query Intelligence Layer** with classification, routing, and feedback loop to Area 1
- **NL Analytics Interface** — managers ask in plain language, get cited structured answers
- **Knowledge Health Dashboard** — powered entirely by Area 2 validation events
- **Proactive Intelligence Agent** — push alerts on spikes, gaps, silos, deprecations
- **Cross-Team Silo Detector** — semantic query overlap detection across RBAC rooms

### Area 4 — Anomaly Detection & Forecasting (Planned Extension)

> Consumes Area 3 query event time-series and Area 2 validation logs. No new data pipelines needed.

- Query Spike Detector (Z-score on rolling 15-minute windows per topic cluster)
- Knowledge Staleness Forecasting (doc ingest timestamps + library release cadence → risk score)
- Escalation Rate Anomaly Detection (control chart on Critic Agent escalation log per team)
- Dependency Risk Forecasting (Poisson model on breaking change frequency per library)

### Area 5 — Knowledge Graph Extraction (Planned Extension)

> Consumes GLiNER entity extractions (Area 2) and Dependency Tracker implicit graph (Area 2). Feeds structured context back to Area 1 RAG pipeline.

- Entity-Relation Extraction at Ingest (extends GLiNER with relation classifier)
- API Dependency Graph (materialises Dependency Tracker as a queryable graph)
- Knowledge Provenance Graph (document → chunk → answer → ticket audit trail)
- Team-Concept Ownership Graph (upgrades Silo Detector from statistical to graph traversal)

---

## 6. Agentic System Design

### Design Philosophy: One Agent, One Tool

Multi-tool agents degrade. When a single agent handles multiple tools, tool selection becomes unreliable, debugging becomes complex, and test isolation becomes impossible.

**Rule: one agent, one responsibility, independently testable.**

Multi-agent orchestration via **LangGraph** implements the **ReAct (Reasoning + Acting)** pattern with a stateful graph.

### Agent Roster

| Agent | Single Responsibility | Interfaces With |
|---|---|---|
| **Orchestrator** | Classify query type, route to correct specialist agent(s), merge results | All agents, query classifier, routing graph |
| **Doc Search Agent** | Semantic + keyword retrieval from T1 Hybrid RAG | Qdrant, page index, BM25, BGE-reranker |
| **Live Doc Agent** | Fetch, parse, temporarily index external URLs and open-source docs | Firecrawl, Tavily, ephemeral chunk store |
| **Jira Ticket Agent** | Query Jira issues, support history, prior resolutions | Jira API, vector index of ticket embeddings |
| **Summariser Agent** | Produce structured document summaries with clause-preservation | Doc Search Agent output, page index, LLM |
| **Analytics Agent** | Translate NL analytics queries into structured log queries | Query log DB, interaction event store, NL-to-SQL |
| **Generator Agent** | Synthesise cited answer from compressed context chunks | Context compression output, LLM, citation builder |
| **Critic Agent** | Evaluate Generator output for grounding, hallucinations, citation completeness | Generator output, retrieved chunks, validation schema |
| **Proactive Agent** | Emit proactive alerts based on Dependency Tracker and gap signals | Dependency Tracker, gap signal DB, notification layer |

### Iterative Execution Loop

```
Retrieve → Analyse → Tool call → Retrieve again
```

Continues until confidence threshold is met or escalation is triggered.

---

## 7. Full Query Pipeline

```
User Query
    │
    ▼
Orchestrator Agent
    │ (classify query type: lookup / summarisation / troubleshooting / comparison / analytics)
    │ (route to specialist agent(s))
    ▼
Specialist Agent(s)
    │ (Doc Search / Live Doc / Jira Ticket / Summariser / Analytics)
    ▼
Context Compression
    │ (post-reranking: merge redundant overlapping chunks before LLM)
    ▼
Generator Agent
    │ (synthesise cited answer with confidence score per claim)
    ▼
Critic Agent
    │ (verify: is every claim grounded? any hallucinations? sources cited?)
    │
    ├── PASS ──▶ Cited answer delivered to user
    │                │
    │                ▼
    │           Interaction logged → Analytics + Knowledge Loop updated
    │
    └── FAIL ──▶ Refine response → re-evaluate
                      │
                      └── Persistent failure ──▶ HITL escalation queue
```

---

## 8. User Roles

| Role | Knowledge Scope | Core Features | Analytics Access |
|---|---|---|---|
| **New Employee** | Onboarding KB only (RBAC-restricted) | Guided onboarding Q&A, role-specific doc recommendations | Personal query history, onboarding checklist |
| **Current Employee** | Team KB + cross-team where permitted | Doc retrieval, summarisation, version-aware answers, live doc fetch | Personal search history, frequently accessed docs |
| **Manager** | Full team scope + inter-team controls | All employee features + RBAC management + HITL approval queue + doc management | Team health dashboard, gap heatmap, search insights, escalation queue |
| **Company Head** | Organisation-wide | All manager features + org-level RBAC + cross-team access management | Full org analytics, silo detection map, hallucination rate, all-team gap analysis |

---

## 9. Design Principles

1. **One agent, one tool** — never assign multiple tools to a single agent
2. **Validation is adversarial** — Generator and Critic are always separate agents
3. **PII never leaves the network** — GLiNER runs locally at ingest time, always
4. **Every interaction is a data point** — query events are logged and feed Area 3 and Area 4
5. **Retrieval beats generation** — prefer grounded retrieved content over LLM synthesis for factual claims
6. **Vertical slice first** — one data source, full pipeline end-to-end, before expanding scope
7. **The five areas are one system** — design each component so its output is consumable by at least one other area

---

*Next: [02_rag_pipeline_and_validation.md](./02_rag_pipeline_and_validation.md)*
