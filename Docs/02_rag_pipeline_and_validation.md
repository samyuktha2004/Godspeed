# 02 · RAG Pipeline, Data Ingestion & Validation

> **Document purpose:** Full technical specification for Areas 1 and 2. Everything a developer needs to implement the retrieval pipeline, ingestion workflow, PII layer, Generator + Critic validation, Knowledge Loop, and Dependency Tracker. Treat each section as a buildable unit.

---

## Table of Contents

1. [Data Sources & Ingestion Pipeline](#1-data-sources--ingestion-pipeline)
2. [Chunking Strategy](#2-chunking-strategy)
3. [T1 — Three-Way Hybrid RAG](#3-t1--three-way-hybrid-rag)
4. [T2 — CAG (Cache-Augmented Generation)](#4-t2--cag-cache-augmented-generation)
5. [T3 — Live Doc Agent](#5-t3--live-doc-agent)
6. [Dual Index Design](#6-dual-index-design)
7. [PII Masking with GLiNER](#7-pii-masking-with-gliner)
8. [Generator + Critic Validation](#8-generator--critic-validation)
9. [Knowledge Loop](#9-knowledge-loop)
10. [Dependency Tracker Pipeline](#10-dependency-tracker-pipeline)
11. [Summariser Failure Modes to Guard Against](#11-summariser-failure-modes-to-guard-against)
12. [Tech Stack Reference](#12-tech-stack-reference)

---

## 1. Data Sources & Ingestion Pipeline

### Supported Sources

| Source | Integration Method | Priority | Notes |
|---|---|---|---|
| **Notion** | Official Notion API (`notion-sdk-py`) | Core | See `04_integrations.md` for full spec |
| **Confluence** | Confluence REST API v2 | Core | See `04_integrations.md` |
| **GitHub** | GitHub REST API + `PyGithub` | Core | READMEs, PRs, issues, wikis, code comments |
| **PDF upload** | User-facing upload button → direct ingest | Core | Internal SOPs, reports, onboarding docs |
| **URLs** | Firecrawl / BeautifulSoup fallback | Core | API docs, external documentation pages |
| **Jira** | Jira REST API | Core | Tickets, issue history, support logs |
| **SharePoint** | Microsoft Graph API | Optional extension | |
| **Google Docs** | Google Drive API v3 | Optional extension | |

### Ingestion Pipeline — 5 Stages

```
Source (Notion / Confluence / GitHub / PDF / URL / Jira)
    │
    ▼
Stage 1: FETCH
    - Notion: page tree traversal via blocks API
    - Confluence: space → page hierarchy via REST
    - GitHub: repo → README + /docs + issues + PRs
    - PDF: direct file upload endpoint
    - URLs: Firecrawl for JS-rendered; requests + BS4 fallback
    │
    ▼
Stage 2: CLEAN & NORMALISE (Docling)
    - Handles: PDF, HTML, markdown, code, tables, multi-column layouts
    - Outputs: clean markdown with preserved structure
    - Docling handles: table extraction, code block detection, header hierarchy
    │
    ▼
Stage 3: PII MASKING (GLiNER — local, zero egress)
    - Runs BEFORE any data enters vector store
    - Detects: names, emails, phone numbers, national IDs, addresses
    - Fine-tuneable for domain-specific entities (internal project codenames, etc.)
    - Covers: GDPR + India DPDP Act + Singapore PDPA
    │
    ▼
Stage 4: SEMANTIC CHUNKING
    - Splits on: sentence and paragraph boundaries
    - 15% overlap at chunk edges (prevents context loss at boundaries)
    - Code blocks: NEVER split mid-block
    - Numbered lists: NEVER split mid-list
    - Target chunk size: 256–512 tokens (configurable per source type)
    │
    ▼
Stage 5: METADATA TAGGING
    - source_uri: original URL or file path
    - source_type: notion | confluence | github | pdf | url | jira
    - ingested_at: ISO timestamp
    - content_hash: SHA256 of raw content (for change detection)
    - rbac_level: public | team:<team_id> | restricted:<user_id>
    - doc_type: sop | runbook | ticket | pr | readme | wiki | api_doc
    - language: ISO 639-1 code (detected automatically)
```

### Why Docling Over Other Parsers

- Handles PDF multi-column layouts that PyMuPDF and pdfplumber destroy
- Preserves table structure as clean markdown tables
- Detects code blocks with language hints (critical for GitHub content)
- Outputs consistent structure regardless of source format

---

## 2. Chunking Strategy

### Why Fixed-Size Chunking is Rejected

Fixed-size splits (e.g. 512 tokens hard boundary) are **explicitly not used**. They destroy:
- Code blocks split mid-function
- Numbered lists split mid-step
- Paragraph context at boundaries
- Table rows split from headers

### Semantic Chunking Implementation

```python
# Pseudocode — actual implementation in src/ingestion/chunker.py
def semantic_chunk(text: str, max_tokens: int = 512, overlap: float = 0.15) -> list[Chunk]:
    # 1. Split into sentences using spaCy sentencizer
    sentences = sentencize(text)
    
    # 2. Group sentences into paragraphs (double newline boundaries)
    paragraphs = group_by_paragraph(sentences)
    
    # 3. Build chunks respecting paragraph boundaries
    chunks = []
    current_chunk = []
    current_tokens = 0
    
    for para in paragraphs:
        para_tokens = count_tokens(para)
        
        # Special case: code blocks and lists are never split
        if is_code_block(para) or is_numbered_list(para):
            if current_tokens + para_tokens > max_tokens:
                chunks.append(flush(current_chunk))
                current_chunk = [para]
                current_tokens = para_tokens
            else:
                current_chunk.append(para)
                current_tokens += para_tokens
            continue
        
        if current_tokens + para_tokens > max_tokens:
            chunks.append(flush(current_chunk))
            # Add 15% overlap from end of previous chunk
            overlap_paras = get_overlap(current_chunk, overlap)
            current_chunk = overlap_paras + [para]
            current_tokens = count_tokens(current_chunk)
        else:
            current_chunk.append(para)
            current_tokens += para_tokens
    
    if current_chunk:
        chunks.append(flush(current_chunk))
    
    return chunks
```

---

## 3. T1 — Three-Way Hybrid RAG

### Why Three-Way

- **Dense semantic search alone** misses exact tokens: error codes, version strings, API names (e.g. `kafka.consumer.ConsumerRecord`, `k8s.io/api/core/v1`)
- **BM25 alone** misses semantic intent: paraphrases, conceptual questions, natural language queries
- **Three-way fusion** covers both gaps simultaneously

IBM research confirms three-way retrieval (dense + sparse + keyword) consistently outperforms two-way on technical domain queries.

### Component Breakdown

#### BGE-M3 (Embeddings)

```python
# Model: BAAI/bge-m3
# Why: single model outputs BOTH dense and sparse vectors in one pass
# License: MIT
# Languages: 100+
# Deployment: CPU and GPU

from FlagEmbedding import BGEM3FlagModel

model = BGEM3FlagModel('BAAI/bge-m3', use_fp16=True)

# Single pass → dense + sparse + colbert vectors
outputs = model.encode(
    texts,
    batch_size=12,
    max_length=8192,
    return_dense=True,
    return_sparse=True,
    return_colbert_vecs=False  # optional, skip for speed
)

dense_vectors = outputs['dense_vecs']      # shape: (N, 1024)
sparse_vectors = outputs['lexical_weights'] # dict of token → weight
```

#### BM25 (Exact Token Matching)

```python
# Library: rank_bm25
# Why: zero infra cost, essential for error codes, version strings, API names
# Install: pip install rank-bm25

from rank_bm25 import BM25Okapi

# At index time:
tokenised_corpus = [doc.split() for doc in corpus]
bm25 = BM25Okapi(tokenised_corpus)

# At query time:
bm25_scores = bm25.get_scores(query.split())
```

#### Reciprocal Rank Fusion (RRF)

```python
def reciprocal_rank_fusion(
    dense_results: list[tuple[str, float]],
    sparse_results: list[tuple[str, float]],
    bm25_results: list[tuple[str, float]],
    k: int = 60
) -> list[tuple[str, float]]:
    """
    Merge three ranked lists via RRF.
    k=60 is the standard constant (Robertson et al.)
    Returns merged ranking without requiring score normalisation.
    """
    scores = {}
    
    for rank, (doc_id, _) in enumerate(dense_results):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
    
    for rank, (doc_id, _) in enumerate(sparse_results):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
    
    for rank, (doc_id, _) in enumerate(bm25_results):
        scores[doc_id] = scores.get(doc_id, 0) + 1 / (k + rank + 1)
    
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

#### BGE-Reranker-v2-m3 (Cross-Encoder)

```python
# Model: BAAI/bge-reranker-v2-m3
# Why: cross-encoder, Apache 2.0, multilingual, ~80ms GPU latency for top-50
# Takes: top 50 from RRF → outputs top 5 for LLM context window

from FlagEmbedding import FlagReranker

reranker = FlagReranker('BAAI/bge-reranker-v2-m3', use_fp16=True)

# Rerank top 50 RRF results to top 5
pairs = [(query, doc) for doc in top_50_docs]
scores = reranker.compute_score(pairs, normalize=True)
top_5 = sorted(zip(top_50_docs, scores), key=lambda x: x[1], reverse=True)[:5]
```

#### Post-Reranking Context Compression

```python
# After reranking, BEFORE sending to LLM:
# 1. Detect overlapping/redundant chunks (cosine similarity > 0.92 threshold)
# 2. Merge overlapping chunks into single information-dense representation
# 3. Summarise merged content using Haiku (cheap, fast)
# 4. Send compressed context to Generator Agent

# Why: fewer tokens, less noise, better response clarity without losing content
# Implementation: src/retrieval/context_compressor.py
```

### Full T1 Pipeline

```
Query
  │
  ├──▶ BGE-M3 encode (dense + sparse) ──▶ Qdrant search (top 50 dense)
  │                                    └──▶ Qdrant sparse search (top 50)
  │
  ├──▶ BM25 search (top 50 exact token)
  │
  ▼
RRF Fusion (merge all three → top 50 unified)
  │
  ▼
BGE-Reranker-v2-m3 (top 50 → top 5)
  │
  ▼
Context Compression (deduplicate + merge redundant chunks)
  │
  ▼
Generator Agent (cited answer synthesis)
```

---

## 4. T2 — CAG (Cache-Augmented Generation)

### The Problem T2 Solves

RAG indexes content on a schedule. There is always a gap between content being created and content being retrievable. Recent sprint summaries, merged PRs, active incidents, and deployment notes are too recent and too fragmented to retrieve well via RAG.

### Implementation

```python
# Nightly job: runs at 02:00 UTC (configurable)
# Script: src/cag/nightly_summariser.py

async def run_nightly_cag(team_id: str):
    # 1. Fetch last 24h of Jira activity for team
    jira_activity = await jira_client.get_recent_activity(
        team_id=team_id,
        since=datetime.utcnow() - timedelta(hours=24),
        types=['issue_created', 'issue_closed', 'comment_added', 'status_changed']
    )
    
    # 2. Fetch last 24h of GitHub activity for team's repos
    github_activity = await github_client.get_recent_activity(
        repos=team_config[team_id]['repos'],
        since=datetime.utcnow() - timedelta(hours=24),
        types=['pull_request_merged', 'issue_closed', 'deployment']
    )
    
    # 3. Summarise with Haiku (cheap: ~$0.0025/1k tokens)
    summary = await llm_haiku.summarise(
        content=format_activity(jira_activity, github_activity),
        instructions="""
        Summarise recent team activity. Keep ALL technical specifics intact:
        - Exact library versions, error messages, API names
        - PR numbers and what they changed
        - Incident details and resolutions
        Collapse ONLY repetitive narrative/status update language.
        Output: structured markdown, max 2000 tokens.
        """
    )
    
    # 4. Store as team context (injected into system prompt at session start)
    await cache.set(
        key=f"cag:team:{team_id}:context",
        value=summary,
        ttl=86400  # 24h, refreshed by next nightly run
    )
```

### Session Injection

```python
# At session start for team member:
team_context = await cache.get(f"cag:team:{user.team_id}:context")

system_prompt = f"""
You are the Enterprise Knowledge Copilot for {user.team_id}.

## Recent Team Activity (last 24h — from CAG pipeline)
{team_context}

## Instructions
Use the above recent context alongside retrieved documents.
Always cite sources. Flag if information is from recent activity vs indexed KB.
"""
```

---

## 5. T3 — Live Doc Agent

### The Primary Differentiator

Every competitor answers from stale training data or snapshots indexed months ago. T3 fetches and answers from actual current documentation — at query time.

**Use cases:**
- Engineer pastes a GitHub URL: `github.com/kubernetes/kubernetes/issues/12345`
- Engineer asks: "What changed in Kubernetes 1.30 that breaks ingress?"
- Engineer asks: "What is the current FastAPI rate limiting API?"
- Dependency Tracker detects a new library version → T3 pre-fetches the changelog

### Implementation

```python
# src/agents/live_doc_agent.py

class LiveDocAgent:
    def __init__(self):
        self.firecrawl = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
        self.tavily = TavilyClient(api_key=settings.TAVILY_API_KEY)
        self.ephemeral_store = EphemeralVectorStore()  # session-scoped
    
    async def fetch_and_index(self, query: str, url: str = None) -> list[Chunk]:
        if url:
            # Direct URL fetch — Firecrawl handles JS-rendered pages
            result = self.firecrawl.scrape_url(
                url,
                params={'formats': ['markdown'], 'onlyMainContent': True}
            )
            content = result['markdown']
            source = url
        else:
            # Web search fallback via Tavily
            results = self.tavily.search(
                query=query,
                search_depth="advanced",
                max_results=5,
                include_raw_content=True
            )
            content = '\n\n'.join([r['raw_content'] for r in results['results']])
            source = [r['url'] for r in results['results']]
        
        # Chunk and embed ephemerally (not persisted to main Qdrant)
        chunks = semantic_chunk(content)
        embeddings = bge_m3.encode([c.text for c in chunks])
        
        # Store in session-scoped ephemeral vector store
        await self.ephemeral_store.add(chunks, embeddings, source=source)
        
        return chunks
    
    async def retrieve(self, query: str) -> list[Chunk]:
        # Search ephemeral store for this session
        return await self.ephemeral_store.search(query, top_k=5)
```

### When T3 is Triggered

```python
# Orchestrator routing logic:
# T3 is triggered when:
# 1. Query contains a URL (auto-detect)
# 2. Query classification = "troubleshooting" + topic is an open-source library
# 3. Query classification = "troubleshooting" + no high-confidence T1 results
# 4. Dependency Tracker pre-trigger (new version detected → fetch changelog proactively)
```

---

## 6. Dual Index Design

Two complementary indexes serve different content types:

| Index | Best For | What It Preserves | Implementation |
|---|---|---|---|
| **Page Index** | PDFs, SOPs, structured internal docs | Document hierarchy — page numbers, section headers, context boundaries. Enables precise citations and section-level summarisation | Custom page-aware chunker + metadata store in PostgreSQL |
| **Vector DB (Qdrant)** | Unstructured text, web content, Jira tickets, Notion pages, GitHub content | Semantic similarity with top-K retrieval, reranking, BGE-M3 multi-vector native support | Qdrant with named vectors: `dense`, `sparse` |

### Qdrant Collection Setup

```python
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, SparseVectorParams

client = QdrantClient(host="localhost", port=6333)

client.create_collection(
    collection_name="enterprise_kb",
    vectors_config={
        "dense": VectorParams(size=1024, distance=Distance.COSINE),
    },
    sparse_vectors_config={
        "sparse": SparseVectorParams()
    }
)

# Insert with both vector types
client.upsert(
    collection_name="enterprise_kb",
    points=[
        PointStruct(
            id=chunk.id,
            vector={
                "dense": dense_vector,
                "sparse": SparseVector(
                    indices=sparse_indices,
                    values=sparse_values
                )
            },
            payload={
                "text": chunk.text,
                "source_uri": chunk.metadata.source_uri,
                "source_type": chunk.metadata.source_type,
                "rbac_level": chunk.metadata.rbac_level,
                "ingested_at": chunk.metadata.ingested_at,
                "content_hash": chunk.metadata.content_hash,
            }
        )
    ]
)
```

---

## 7. PII Masking with GLiNER

### Why GLiNER Over Cloud NER

| Criterion | GLiNER | AWS Comprehend / Google NLP |
|---|---|---|
| Data egress | Zero — runs locally | Data sent to cloud ✗ |
| GDPR compliance | Yes | Requires additional DPA ✗ |
| DPDP Act (India) | Yes | Requires transfer assessment ✗ |
| Fine-tunable | Yes — for domain entities | Limited |
| Cost | One-time model load | Per-token pricing |
| Latency | ~50ms per chunk on CPU | ~200ms + network |

### Implementation

```python
# src/ingestion/pii_masker.py
from gliner import GLiNER

model = GLiNER.from_pretrained("urchade/gliner_medium-v2.1")

# Entity types to detect and mask
ENTITY_TYPES = [
    "PERSON",           # Names
    "EMAIL",            # Email addresses
    "PHONE",            # Phone numbers
    "ID_NUMBER",        # National IDs, Aadhaar, passport
    "ADDRESS",          # Physical addresses
    "ORGANIZATION",     # Company names (optional — context-dependent)
    "DATE_OF_BIRTH",    # DOB
    "BANK_ACCOUNT",     # Financial identifiers
    # Domain-specific — fine-tune for these:
    "INTERNAL_PROJECT", # Internal codename e.g. "Project Phoenix"
    "EMPLOYEE_ID",      # Internal employee IDs
]

def mask_pii(text: str) -> tuple[str, list[PIIEvent]]:
    entities = model.predict_entities(text, ENTITY_TYPES, threshold=0.5)
    
    masked_text = text
    pii_events = []
    
    # Replace detected entities with typed placeholders
    for entity in sorted(entities, key=lambda x: x['start'], reverse=True):
        placeholder = f"[{entity['label']}]"
        masked_text = (
            masked_text[:entity['start']] +
            placeholder +
            masked_text[entity['end']:]
        )
        pii_events.append(PIIEvent(
            entity_type=entity['label'],
            source_uri=source_uri,
            detected_at=datetime.utcnow()
        ))
    
    return masked_text, pii_events

# PII events are logged to Area 3 health dashboard
# (compliance metric: PII risk events by source type)
```

### Fine-tuning for Domain Entities

```python
# For domain-specific entity types (internal project names, product codenames):
# 1. Create labelled examples in data/pii_training/domain_entities.jsonl
# 2. Fine-tune: python scripts/finetune_gliner.py --data data/pii_training/
# 3. Model saved to models/gliner_domain_finetuned/
# Time estimate: ~2h on single GPU for 500 examples
```

---

## 8. Generator + Critic Validation

### Why Adversarial Validation

Having a model validate its own output is a structural conflict of interest. Separation of generation and validation into two independent agents is the strongest architectural response to the hallucination problem.

Stanford 2025 research confirms: even state-of-the-art RAG systems hallucinate 17–33% of the time in specialised domains. Adversarial validation is not optional — it is the core trust mechanism of the system.

### Generator Agent

```python
# src/agents/generator_agent.py

GENERATOR_SYSTEM_PROMPT = """
You are the Generator Agent for Enterprise Knowledge Copilot.
Your job: synthesise a precise, cited answer from the provided context chunks.

Rules:
1. ONLY use information present in the provided context chunks.
2. For EVERY factual claim, cite the specific source chunk using [Source: <uri>].
3. Assign a confidence score (0.0–1.0) to each claim based on how directly it is supported.
4. If the context is insufficient to answer, state this explicitly — do not guess.
5. Never add information from your training data. Context chunks are your ONLY source.
6. Preserve all technical specifics: exact version numbers, error codes, API names.

Output format:
{
  "answer": "...",
  "claims": [
    {"text": "...", "source_uri": "...", "confidence": 0.95},
    ...
  ],
  "overall_confidence": 0.87,
  "context_sufficient": true
}
"""
```

### Critic Agent

```python
# src/agents/critic_agent.py

CRITIC_SYSTEM_PROMPT = """
You are the Critic Agent for Enterprise Knowledge Copilot.
Your job: evaluate whether the Generator's answer is grounded in the provided source chunks.

For each claim in the Generator's output, verify:
1. GROUNDED: Is this claim directly supported by at least one source chunk?
2. HALLUCINATED: Does this claim contain information NOT present in any source chunk?
3. CITED: Is the correct source chunk cited for this claim?
4. SCOPE_BLEED: Does this claim merge content from two sources into a meaning neither supports alone?

Output format:
{
  "verdict": "pass" | "fail" | "escalate",
  "claim_verdicts": [
    {
      "claim": "...",
      "verdict": "grounded" | "hallucinated" | "scope_bleed" | "uncited",
      "evidence_chunk": "...",
      "notes": "..."
    }
  ],
  "overall_confidence": 0.91,
  "escalation_reason": null | "insufficient_context" | "conflicting_sources" | "out_of_scope"
}
"""
```

### Decision Gate

```python
# src/validation/decision_gate.py

async def validate_response(
    generator_output: GeneratorOutput,
    critic_output: CriticOutput
) -> ValidationResult:
    
    if critic_output.verdict == "pass":
        return ValidationResult(
            status="deliver",
            answer=generator_output.answer,
            confidence=critic_output.overall_confidence
        )
    
    elif critic_output.verdict == "fail":
        # Attempt one refinement cycle
        refined = await generator_agent.refine(
            original=generator_output,
            critic_feedback=critic_output.claim_verdicts
        )
        re_eval = await critic_agent.evaluate(refined)
        
        if re_eval.verdict == "pass":
            return ValidationResult(status="deliver", answer=refined.answer)
        else:
            return ValidationResult(status="escalate", reason=re_eval.escalation_reason)
    
    elif critic_output.verdict == "escalate":
        # Log to HITL queue
        await hitl_queue.add(EscalationEvent(
            query=query,
            generator_output=generator_output,
            critic_output=critic_output,
            team_id=user.team_id,
            timestamp=datetime.utcnow()
        ))
        return ValidationResult(
            status="escalate",
            message="This query has been escalated for human review."
        )
```

---

## 9. Knowledge Loop

Every resolved query becomes part of the system's memory and feeds back into retrieval quality.

```
Validated Answer Delivered
    │
    ▼
Auto-create Ticket Record:
    {
        "query": original user input,
        "fix": validated response text,
        "source_uris": cited sources,
        "confidence": critic confidence score,
        "team_id": team context,
        "timestamp": ISO,
        "topic_cluster": classifier output
    }
    │
    ▼
Index ticket into Qdrant (same pipeline as other content)
    │
    ├──▶ Future similar queries → retrieve this ticket as high-quality prior answer
    │
    ├──▶ Frequently answered topics → retrieval rank boost (nightly weight update)
    │
    └──▶ Low-confidence / escalated queries → knowledge gap signal
              │
              ▼
         Gap Signal DB (consumed by Area 3 Analytics and Area 4 Anomaly Detection)
```

---

## 10. Dependency Tracker Pipeline

### Purpose

Monitor upstream open-source dependencies and map breaking changes to internal codebases before production breaks.

### Smart Polling Strategy

**Do NOT use continuous surveillance.** Check repos on-demand when searched. Fall back to scheduled checks based on library release cadence. This saves significant infrastructure cost.

```python
# src/dependency_tracker/poller.py

async def check_dependency(library: str, trigger: str = "on_demand") -> DiffResult:
    """
    trigger: "on_demand" (user queried about this library)
           | "scheduled" (library is on watchlist, due for check)
           | "proactive" (Area 4 risk score triggered pre-check)
    """
    
    # 1. Fetch current snapshot
    repo_url = registry.get_repo_url(library)
    current_snapshot = await fetch_snapshot(repo_url)
    
    # 2. Compare with stored snapshot
    previous_snapshot = await snapshot_store.get(library)
    
    if current_snapshot.hash == previous_snapshot.hash:
        return DiffResult(changed=False)
    
    # 3. Diff and classify changes
    diff = compute_diff(previous_snapshot, current_snapshot)
    classified = await classify_changes(diff)
    
    # 4. Store new snapshot
    await snapshot_store.set(library, current_snapshot)
    
    return classified
```

### Four-Stage Pipeline

```
Stage 1: INGEST & SNAPSHOT
    - Clone/pull GitHub repo for each registered dependency
    - Fetch API docs URL
    - Store: content_hash + timestamp + version tag
    - Diff basis: compare new snapshot vs stored on next run

Stage 2: DIFF & CLASSIFY (tree-sitter + difflib)
    - AST-level diff for code changes (tree-sitter)
    - Structured text diff for doc changes (difflib)
    - Classification:
        DEPRECATED    → symbol marked as deprecated, replacement specified
        SIGNATURE_CHANGED → function signature modified (new params, types changed)
        RENAMED       → symbol renamed
        REMOVED       → symbol removed entirely
        INFORMATIONAL → docs updated, no breaking change

Stage 3: IMPACT SCAN (ripgrep + tree-sitter)
    - Scan all internal repos and doc folders
    - For each affected symbol:
        file_path: src/services/payment_service.py
        line_number: 142
        current_usage: old_api.connect(host, timeout=30)
        required_change: SIGNATURE_CHANGED
        suggested_fix: new_api.connect(host, timeout=30, retry=True)

Stage 4: REPORT & PATCH
    HIGH confidence (exact rename, added param with default):
        → Apply codemod automatically
        → Open PR with migration report as description
        → Human reviews PR (never auto-merge)
    
    LOW confidence (ambiguous change, multiple possible fixes):
        → Generate migration report only (markdown + JSON)
        → Flag for human review in HITL queue
        → No auto-patch
```

### LLM Fallback for Unstructured Changelogs

```python
# When changelog format is unstructured (no AST, prose only):
async def extract_from_changelog(changelog_text: str) -> list[BreakingChange]:
    response = await llm_haiku.structured_output(
        prompt=f"""
        Extract ALL breaking changes, deprecations, and signature changes from this changelog.
        
        Changelog:
        {changelog_text}
        
        Return JSON array:
        [{{
            "symbol": "function/class/method name",
            "change_type": "deprecated|renamed|removed|signature_changed",
            "old_usage": "...",
            "new_usage": "...",
            "migration_notes": "..."
        }}]
        
        Return ONLY valid JSON. No markdown, no preamble.
        """,
        output_schema=list[BreakingChange]
    )
    return response
```

---

## 11. Summariser Failure Modes to Guard Against

These are known failure modes that the Generator + Critic pipeline must explicitly check for:

| Failure Mode | Description | Critic Check |
|---|---|---|
| **Clause omission** | AI drops entire clause when compressing a multi-clause document | Critic verifies all binding obligations from source appear in summary |
| **Scope bleed** | Answer merges content from two docs into meaning neither actually supports | Critic flags any claim that cannot be traced to a single source chunk |
| **Condition dropping** | Multi-condition obligations lose one or more conditions silently | Critic checks that conditional logic (`if X then Y`) is fully preserved |
| **Hedged hallucination** | System confidently answers from additional documents when query was restricted to specific docs | Critic verifies all cited sources are within the query's authorised scope |

---

## 12. Tech Stack Reference

| Layer | Technology | Version | Notes |
|---|---|---|---|
| Embeddings | `BAAI/bge-m3` | Latest | Dense + sparse in one pass |
| Reranker | `BAAI/bge-reranker-v2-m3` | Latest | Apache 2.0 |
| Vector DB | Qdrant | 1.9+ | Docker deployable, multi-vector native |
| Fallback Vector DB | ChromaDB | 0.5+ | For local dev only |
| PII / NER | GLiNER `urchade/gliner_medium-v2.1` | Latest | Local, zero egress |
| Doc parsing | Docling | Latest | PDF, HTML, markdown, code |
| Orchestration | LangGraph | 0.2+ | Stateful, ReAct pattern |
| Live fetch | Firecrawl SDK | Latest | JS-rendered docs |
| Web search | Tavily Python | Latest | Fallback + multi-source |
| Code parsing | tree-sitter | 0.21+ | AST-level diff |
| Code search | ripgrep (`rg`) | 14+ | Fast codebase scan |
| LLM primary | Claude Sonnet / Gemini Pro | Latest | Answer synthesis |
| LLM fast | Claude Haiku | Latest | Guardrails, CAG, classification |
| Database | PostgreSQL 16 | Latest | Page index, interaction log |
| Cache | Redis 7 | Latest | CAG context store, session data |
| API | FastAPI | 0.111+ | REST API layer |
| Container | Docker + Docker Compose | Latest | Single-machine deployment |

---

*Previous: [01_problem_and_architecture.md](./01_problem_and_architecture.md)*
*Next: [03_analytics_and_intelligence.md](./03_analytics_and_intelligence.md)*
