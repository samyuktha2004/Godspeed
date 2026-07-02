# /docs — Enterprise Knowledge Copilot

> Living documentation for the Enterprise Knowledge Copilot system.

---

## Start here (current, accurate)

| File | Contents |
|---|---|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | System-wide architecture — backend/frontend directory structure, API contract, data flow, deployment |
| [`../agent/README.md`](../agent/README.md) | The real query pipeline: router → planner → retrieval agents → join → synthesiser → guardrail |
| [`TECHSTACK.md`](./TECHSTACK.md) | Current tech stack (Gemini, Qdrant, Neo4j, Redis, Supabase — no Claude/OpenAI dependency) |
| [`INPUTMETHODS.md`](./INPUTMETHODS.md) | Every data source integration, explicitly flagged Implemented vs Design-only |
| [`PRD.md`](./PRD.md) | Shipped frontend feature spec + known gaps |
| [`TODO.md`](./TODO.md) | Frontend build log + outstanding work |
| [`anomaly-and-forecasting/`](./anomaly-and-forecasting/README.md) | Area 4 (anomaly detection) — implemented, accurate |
| [`metadata-scaling-up/`](./metadata-scaling-up/README.md) | Query routing, RBAC channel isolation, retrieval scaling — implemented, accurate, and has the most current pipeline diagram |

## Original vision docs (superseded — historical only)

The original pre-implementation design docs (`01`–`04`) have been removed after their content was fully absorbed elsewhere: still-accurate rationale migrated into `TECHSTACK.md` and `agent/README.md`, real gaps migrated into `TODO.md` with concrete build plans, and "why we didn't build X" decision rationale migrated into `ARCHITECTURE.md`'s "Design Decisions Not Taken" section. Only `05_market_strategy_and_gtm.md` remains, since it's business/GTM content rather than an engineering spec:

| File | What's still useful in it |
|---|---|
| [`05_market_strategy_and_gtm.md`](./05_market_strategy_and_gtm.md) | Market/competitor/GTM analysis (business content, still relevant; a few USP pitches were corrected for accuracy) |

---

## Key Architectural Decisions (current)

- One agent, one tool (never multi-tool agents)
- GLiNER runs locally — zero data egress, always
- A single guardrail agent validates the synthesised answer against sources before delivery
- Soft routing: the deterministic router only narrows scope at high confidence — a correct answer can never become unreachable
- Semantic chunking only — no fixed-size splits
