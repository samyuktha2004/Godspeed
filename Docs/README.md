# /docs — Enterprise Knowledge Copilot

> Living documentation for the Enterprise Knowledge Copilot system. Read in order before writing code. Update when architecture changes.

---

## Document Map

| File | Contents | Read When |
|---|---|---|
| [`01_problem_and_architecture.md`](./01_problem_and_architecture.md) | Problem statement, objectives, system overview, all 5 areas, agentic design, user roles, design principles | **First. Always read this first.** |
| [`02_rag_pipeline_and_validation.md`](./02_rag_pipeline_and_validation.md) | Ingestion pipeline, chunking, T1/T2/T3 retrieval, dual index, GLiNER PII, Generator+Critic validation, Knowledge Loop, Dependency Tracker | Building ingestion, retrieval, or validation components |
| [`03_analytics_and_intelligence.md`](./03_analytics_and_intelligence.md) | Query classification, interaction log schema, retrieval feedback loop, NL analytics, health dashboard, proactive agent, silo detector, Areas 4 & 5 planned specs | Building analytics, dashboards, or Area 3 agents |
| [`04_integrations_and_tech_stack.md`](./04_integrations_and_tech_stack.md) | Notion, Confluence, GitHub integration specs with full code; RBAC enforcement; change detection; tech stack; local dev setup; env vars | Building any integration or setting up development environment |
| [`05_market_strategy_and_gtm.md`](./05_market_strategy_and_gtm.md) | Target customer, tool strategy, competitor analysis, USPs, country-by-country market analysis, GTM sequencing | Product, positioning, or expansion decisions |

---

## The Five Focus Areas at a Glance

```
Area 1 — Hybrid RAG System          [Core — In Scope]
Area 2 — Data Pipelines & Validation [Core — In Scope]
Area 3 — Analytics & NL Intelligence [Core — In Scope]
Area 4 — Anomaly & Forecasting       [Planned Extension]
Area 5 — Knowledge Graph             [Planned Extension]
```

All five areas are one system — not five products. See `01_problem_and_architecture.md` for the interaction map.

---

## Quick Reference

### Primary Tool Integrations
- **Notion** → `04_integrations_and_tech_stack.md#2-notion-integration`
- **Confluence** → `04_integrations_and_tech_stack.md#3-confluence-integration`
- **GitHub** → `04_integrations_and_tech_stack.md#4-github-integration`

### Key Architectural Decisions
- One agent, one tool (never multi-tool agents)
- GLiNER runs locally — zero data egress, always
- Generator and Critic are always separate agents
- Semantic chunking only — no fixed-size splits
- Every interaction is a logged data point feeding Area 3

### Launch Markets
1. 🇮🇳 India — DPDP compliance moat, zero competition, perfect tool stack
2. 🇸🇬 Singapore — SEA regional HQ beachhead
3. 🇦🇺 Australia — English-language, Privacy Act reform, same tool stack
