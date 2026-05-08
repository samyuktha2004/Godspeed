# Godspeed — Enterprise Knowledge Copilot

## What is Godspeed?

Godspeed is an AI-powered Enterprise Knowledge Copilot built by a team of engineers to help organizations search, retrieve, and reason over their internal knowledge. It ingests documents from Confluence, Jira, GitHub, and uploaded files, then uses a multi-agent LangGraph pipeline backed by Google Gemini to answer natural language questions with citations.

## Core Problem

Enterprise teams lose hours every week hunting for information scattered across Confluence wikis, Jira tickets, GitHub repos, and internal PDFs. Godspeed unifies all of this into a single queryable knowledge base with real-time answers.

## Key Features

- **Hybrid Search**: Combines dense vector search (BGE-M3), sparse lexical search, and BM25 for maximum recall
- **Reranking**: BGE-reranker-v2-m3 scores retrieved chunks by relevance before synthesis
- **PII Masking**: GLiNER model automatically redacts personal data before any external API call
- **Multi-Agent Orchestration**: LangGraph graph with parallel retrieval agents (doc_search, ticket_lookup, live_docs)
- **Streaming Answers**: Server-Sent Events (SSE) stream the answer token by token to the client
- **Knowledge Graph**: Neo4j graph of entities (Services, Libraries, Incidents, Teams) extracted from documents
- **Guardrail**: Gemini Flash scores every answer for safety before delivery
- **CAG Snapshots**: Nightly Celery job builds a Context-Augmented Generation snapshot per team

## Tech Stack

- **Orchestration**: LangGraph + LangChain + Google Gemini 2.5 Pro/Flash
- **Embeddings**: BAAI/bge-m3 (1024-dim dense + sparse lexical weights)
- **Reranker**: BAAI/bge-reranker-v2-m3
- **Vector DB**: Qdrant (hybrid dense + sparse collection)
- **Metadata DB**: Supabase (PostgreSQL with RLS)
- **Graph DB**: Neo4j (entity relationships)
- **Task Queue**: Celery + Redis
- **API**: FastAPI with SSE streaming
- **PII**: GLiNER mediumv2.1

## Team

- Adithya Vardan — Backend architecture, agent orchestration, ingestion pipeline
- Samyuktha — Project coordination, documentation
- Ananth Shyam — Jira agent, Confluence agent, File agent, integration
