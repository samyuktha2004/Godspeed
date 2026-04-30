# 04 · Integrations & Tech Stack

> **Document purpose:** Complete integration specifications for the three primary data source tools (Notion, Confluence, GitHub), plus the full tech stack with setup instructions, configuration, and rationale. This is the reference for the ingestion layer.

---

## Table of Contents

1. [Integration Strategy](#1-integration-strategy)
2. [Notion Integration](#2-notion-integration)
3. [Confluence Integration](#3-confluence-integration)
4. [GitHub Integration](#4-github-integration)
5. [Secondary Integrations (Jira, PDF, URL)](#5-secondary-integrations-jira-pdf-url)
6. [RBAC Enforcement Across Sources](#6-rbac-enforcement-across-sources)
7. [Change Detection & Re-indexing](#7-change-detection--re-indexing)
8. [Full Tech Stack Reference](#8-full-tech-stack-reference)
9. [Local Development Setup](#9-local-development-setup)
10. [Environment Variables](#10-environment-variables)

---

## 1. Integration Strategy

### Why These Three Tools First

| Tool | Why First | Startup Profile |
|---|---|---|
| **Notion** | Default knowledge base for 50-100 person startups. Onboarding docs, SOPs, meeting notes, project specs all live here. Notion API is excellent. Notion AI exists but is shallow — massive gap to fill. | Ops-heavy, non-technical teams use this daily |
| **Confluence** | Default for engineering-heavy startups, especially those using Jira. Contains runbooks, architecture docs, sprint notes. Search is notoriously terrible — direct pain point. | Engineering teams, Atlassian-stack companies |
| **GitHub** | Every tech startup uses this. PRs, issues, READMEs, wikis, code comments contain enormous institutional knowledge. "Why was this built this way?" is never answered without this. | All technical teams |

### Source-Neutral Document Model

All three integrations output to the same internal document model before entering the ingestion pipeline:

```python
@dataclass
class RawDocument:
    uri: str              # Unique identifier (Notion page ID / Confluence page ID / GitHub URL)
    source_type: str      # "notion" | "confluence" | "github" | "pdf" | "url" | "jira"
    title: str
    content: str          # Raw content (markdown or plain text)
    content_hash: str     # SHA256 — used for change detection
    created_at: datetime
    updated_at: datetime
    author_ids: list[str] # Source-native user IDs (for RBAC mapping)
    space_id: str         # Notion workspace / Confluence space / GitHub org
    parent_ids: list[str] # For hierarchy-aware citation (Notion parent / Confluence parent page)
    tags: list[str]       # Source-native labels/tags
    raw_metadata: dict    # Full source-native metadata (source-specific fields)
```

---

## 2. Notion Integration

### Authentication

```python
# Integration type: Official Notion API (Internal Integration)
# Auth: Bearer token (Notion integration token)
# SDK: notion-sdk-py

from notion_client import AsyncClient

notion = AsyncClient(auth=settings.NOTION_INTEGRATION_TOKEN)
```

### Page Tree Traversal

Notion organises content as a tree: Database → Pages → Sub-pages → Blocks. Full traversal is required to capture all content.

```python
# src/integrations/notion/crawler.py

class NotionCrawler:
    
    async def crawl_workspace(self, space_id: str) -> list[RawDocument]:
        """
        Crawl entire Notion workspace accessible to the integration token.
        Respects page hierarchy for context-aware citation.
        """
        docs = []
        
        # 1. Search all pages (Notion API search endpoint)
        cursor = None
        while True:
            response = await notion.search(
                filter={"property": "object", "value": "page"},
                sort={"direction": "descending", "timestamp": "last_edited_time"},
                start_cursor=cursor,
                page_size=100
            )
            
            for page in response['results']:
                doc = await self.fetch_page(page['id'], page)
                if doc:
                    docs.append(doc)
            
            if not response['has_more']:
                break
            cursor = response['next_cursor']
        
        return docs
    
    async def fetch_page(self, page_id: str, page_metadata: dict) -> RawDocument | None:
        try:
            # Fetch page properties (title, created_by, etc.)
            page = await notion.pages.retrieve(page_id=page_id)
            
            # Fetch all blocks (content)
            content_blocks = await self._fetch_all_blocks(page_id)
            
            # Convert blocks to markdown
            content_md = self._blocks_to_markdown(content_blocks)
            
            if not content_md.strip():
                return None  # Skip empty pages
            
            return RawDocument(
                uri=f"notion://{page_id}",
                source_type="notion",
                title=self._extract_title(page),
                content=content_md,
                content_hash=sha256(content_md.encode()).hexdigest(),
                created_at=datetime.fromisoformat(page['created_time'].rstrip('Z')),
                updated_at=datetime.fromisoformat(page['last_edited_time'].rstrip('Z')),
                author_ids=[page['created_by']['id']],
                space_id=space_id,
                parent_ids=self._get_parent_chain(page),
                tags=self._extract_tags(page),
                raw_metadata=page
            )
        except APIResponseError as e:
            logger.warning(f"Failed to fetch Notion page {page_id}: {e}")
            return None
    
    async def _fetch_all_blocks(self, block_id: str) -> list[dict]:
        """Recursively fetch all blocks including nested children."""
        blocks = []
        cursor = None
        
        while True:
            response = await notion.blocks.children.list(
                block_id=block_id,
                start_cursor=cursor,
                page_size=100
            )
            
            for block in response['results']:
                blocks.append(block)
                # Recurse into children (toggles, callouts, columns)
                if block.get('has_children'):
                    child_blocks = await self._fetch_all_blocks(block['id'])
                    blocks.extend(child_blocks)
            
            if not response['has_more']:
                break
            cursor = response['next_cursor']
        
        return blocks
    
    def _blocks_to_markdown(self, blocks: list[dict]) -> str:
        """Convert Notion blocks to clean markdown."""
        lines = []
        
        BLOCK_CONVERTERS = {
            'heading_1': lambda b: f"# {self._rich_text(b['heading_1']['rich_text'])}",
            'heading_2': lambda b: f"## {self._rich_text(b['heading_2']['rich_text'])}",
            'heading_3': lambda b: f"### {self._rich_text(b['heading_3']['rich_text'])}",
            'paragraph': lambda b: self._rich_text(b['paragraph']['rich_text']),
            'bulleted_list_item': lambda b: f"- {self._rich_text(b['bulleted_list_item']['rich_text'])}",
            'numbered_list_item': lambda b: f"1. {self._rich_text(b['numbered_list_item']['rich_text'])}",
            'code': lambda b: f"```{b['code']['language']}\n{self._rich_text(b['code']['rich_text'])}\n```",
            'quote': lambda b: f"> {self._rich_text(b['quote']['rich_text'])}",
            'callout': lambda b: f"> **Note:** {self._rich_text(b['callout']['rich_text'])}",
            'divider': lambda b: "---",
            'table_row': lambda b: self._table_row(b),
            'toggle': lambda b: f"**{self._rich_text(b['toggle']['rich_text'])}**",
        }
        
        for block in blocks:
            block_type = block['type']
            converter = BLOCK_CONVERTERS.get(block_type)
            if converter:
                lines.append(converter(block))
        
        return '\n\n'.join(filter(None, lines))
```

### Incremental Sync (Change Detection)

```python
# src/integrations/notion/sync.py

async def sync_notion_incremental(space_id: str, last_sync_at: datetime):
    """
    Only fetch pages modified since last sync.
    Uses Notion's last_edited_time filter.
    """
    response = await notion.search(
        filter={"property": "object", "value": "page"},
        sort={"direction": "descending", "timestamp": "last_edited_time"},
        query=""  # Empty query = all pages
    )
    
    updated_pages = [
        p for p in response['results']
        if datetime.fromisoformat(p['last_edited_time'].rstrip('Z')) > last_sync_at
    ]
    
    for page in updated_pages:
        new_doc = await crawler.fetch_page(page['id'], page)
        stored_hash = await doc_store.get_hash(f"notion://{page['id']}")
        
        if new_doc.content_hash != stored_hash:
            # Content actually changed (not just metadata)
            await ingest_pipeline.run(new_doc)
            await proactive_agent.check_if_answers_need_invalidation(
                source_uri=f"notion://{page['id']}"
            )

# Sync schedule: every 30 minutes for active workspaces
# Full re-crawl: weekly (Sunday 03:00 UTC)
```

### Notion-Specific Limitations

```
⚠️  Databases: Notion databases are crawled as a collection of pages.
    Database properties (select, relation, etc.) are included as YAML frontmatter.
    Database views are NOT indexed (no structured query support).

⚠️  Embedded files: File blocks (PDFs embedded in Notion) are NOT auto-indexed.
    They require the user to also upload them via the PDF upload endpoint.

⚠️  Permissions: Only pages accessible to the integration token are indexed.
    Private pages (user-private, not shared with integration) are excluded.
    Ensure teams share relevant pages with the Notion integration.
```

---

## 3. Confluence Integration

### Authentication

```python
# Integration type: Confluence REST API v2
# Auth: API token (basic auth with email + token) OR OAuth 2.0 (for Confluence Cloud)
# SDK: atlassian-python-api or direct requests

from atlassian import Confluence

confluence = Confluence(
    url=settings.CONFLUENCE_URL,       # https://yourcompany.atlassian.net
    username=settings.CONFLUENCE_EMAIL,
    password=settings.CONFLUENCE_API_TOKEN,
    cloud=True
)
```

### Space and Page Hierarchy Traversal

Confluence organises content as: Space → Pages → Child Pages → Attachments

```python
# src/integrations/confluence/crawler.py

class ConfluenceCrawler:
    
    async def crawl_space(self, space_key: str) -> list[RawDocument]:
        """Crawl all pages in a Confluence space."""
        docs = []
        
        # Get all pages in space (pagination required)
        start = 0
        limit = 50
        
        while True:
            pages = self.confluence.get_all_pages_from_space(
                space=space_key,
                start=start,
                limit=limit,
                expand='body.storage,version,ancestors,metadata.labels'
            )
            
            if not pages:
                break
            
            for page in pages:
                doc = self._page_to_document(page, space_key)
                docs.append(doc)
            
            start += limit
        
        return docs
    
    def _page_to_document(self, page: dict, space_key: str) -> RawDocument:
        # Convert Confluence Storage Format (XML-based) to clean markdown
        html_content = page['body']['storage']['value']
        markdown_content = self._storage_format_to_markdown(html_content)
        
        return RawDocument(
            uri=f"confluence://{page['id']}",
            source_type="confluence",
            title=page['title'],
            content=markdown_content,
            content_hash=sha256(markdown_content.encode()).hexdigest(),
            created_at=datetime.fromisoformat(page['version']['when'].rstrip('Z')),
            updated_at=datetime.fromisoformat(page['version']['when'].rstrip('Z')),
            author_ids=[page['version']['by']['accountId']],
            space_id=space_key,
            parent_ids=[a['id'] for a in page.get('ancestors', [])],
            tags=[l['name'] for l in page.get('metadata', {}).get('labels', {}).get('results', [])],
            raw_metadata=page
        )
    
    def _storage_format_to_markdown(self, storage_xml: str) -> str:
        """
        Convert Confluence Storage Format (XHTML-based) to clean markdown.
        Handles: structured macros, code blocks, tables, info/warning/note panels.
        """
        from bs4 import BeautifulSoup
        import markdownify
        
        soup = BeautifulSoup(storage_xml, 'html.parser')
        
        # Handle Confluence-specific macros
        for macro in soup.find_all('ac:structured-macro'):
            macro_name = macro.get('ac:name', '')
            
            if macro_name == 'code':
                language = macro.find('ac:parameter', {'ac:name': 'language'})
                lang = language.text if language else ''
                body = macro.find('ac:plain-text-body')
                code = body.text if body else ''
                macro.replace_with(soup.new_tag('pre'))
                macro.string = f"```{lang}\n{code}\n```"
            
            elif macro_name in ['info', 'warning', 'note', 'tip']:
                body = macro.find('ac:rich-text-body')
                if body:
                    macro.replace_with(f"> **{macro_name.upper()}:** {body.get_text()}")
        
        # Convert remaining HTML to markdown
        return markdownify.markdownify(str(soup), heading_style="ATX").strip()
```

### Confluence-Specific Features

```python
# Confluence page hierarchy → section-aware citation
# Use ancestors array to build full path: "Engineering > Backend > API Docs > Rate Limiting"

def build_citation_path(page: dict, space_title: str) -> str:
    ancestors = page.get('ancestors', [])
    path_parts = [space_title] + [a['title'] for a in ancestors] + [page['title']]
    return ' > '.join(path_parts)

# This citation path is stored in chunk metadata and shown to users:
# Source: Engineering > Backend > API Docs > Rate Limiting (Page 3)
```

### Confluence-Specific Limitations

```
⚠️  Attachments: PDF/Word attachments in Confluence pages are NOT auto-indexed.
    They are logged as available attachments but require manual PDF upload.

⚠️  Personal spaces: Personal Confluence spaces (user:~accountId) are excluded
    by default. Only team spaces (TEC, PROD, ENG, etc.) are indexed.
    Configure CONFLUENCE_EXCLUDED_SPACES in environment to control this.

⚠️  Storage format macros: Some complex macros (JIRA issue lists, page trees,
    dynamic content) are converted to static text. Dynamic content is not updated
    in real time — depends on the incremental sync schedule.

⚠️  Rate limits: Atlassian Cloud enforces 200 requests/minute per token.
    Crawler implements exponential backoff automatically.
```

---

## 4. GitHub Integration

### Authentication

```python
# Integration type: GitHub REST API + GraphQL API
# Auth: GitHub App (preferred) or Personal Access Token
# SDK: PyGithub for REST, httpx for GraphQL

from github import Github

github = Github(settings.GITHUB_TOKEN)
# OR GitHub App authentication (preferred for org-level access):
# github = Github(jwt=app_jwt_token)
```

### What to Index from GitHub

GitHub contains multiple content types — each requires different handling:

```python
GITHUB_CONTENT_TYPES = {
    "readme": {
        "path_pattern": "README*.md",
        "description": "Service overview, setup instructions, architecture notes",
        "priority": "high"
    },
    "docs_folder": {
        "path_pattern": "docs/**/*.md",
        "description": "Technical documentation, ADRs, runbooks in /docs",
        "priority": "high"
    },
    "wiki": {
        "source": "wiki_repo",
        "description": "GitHub Wiki pages",
        "priority": "medium"
    },
    "pull_requests": {
        "states": ["merged"],
        "body_only": True,
        "description": "PR descriptions contain architectural context and decision rationale",
        "priority": "medium",
        "max_age_days": 365  # Only last 12 months
    },
    "issues": {
        "states": ["closed"],
        "labels_filter": ["bug", "breaking-change", "deprecation"],
        "description": "Closed issues with specific labels for context",
        "priority": "medium"
    },
    "changelog": {
        "path_pattern": "CHANGELOG*.md",
        "description": "Release notes and breaking change history",
        "priority": "high"  # Critical for Dependency Tracker
    },
    "code_comments": {
        "enabled": False,  # Off by default — too noisy
        "description": "Inline code comments (docstrings, TODO, FIXME)",
        "priority": "low"
    }
}
```

### Repository Crawler

```python
# src/integrations/github/crawler.py

class GitHubCrawler:
    
    async def crawl_repo(self, repo_full_name: str) -> list[RawDocument]:
        """
        repo_full_name: "org/repo-name"
        """
        docs = []
        repo = self.github.get_repo(repo_full_name)
        
        # 1. README
        try:
            readme = repo.get_readme()
            docs.append(self._file_to_document(readme, repo, content_type="readme"))
        except Exception:
            pass
        
        # 2. /docs folder (recursive)
        docs.extend(await self._crawl_docs_folder(repo))
        
        # 3. CHANGELOG
        try:
            changelog = repo.get_contents("CHANGELOG.md")
            docs.append(self._file_to_document(changelog, repo, content_type="changelog"))
        except Exception:
            pass
        
        # 4. Merged PRs (last 12 months, body only)
        docs.extend(await self._crawl_prs(repo, max_age_days=365))
        
        # 5. Closed issues with relevant labels
        docs.extend(await self._crawl_issues(
            repo,
            labels=["bug", "breaking-change", "deprecation", "documentation"]
        ))
        
        # 6. Wiki (if enabled)
        if repo.has_wiki:
            docs.extend(await self._crawl_wiki(repo))
        
        return docs
    
    async def _crawl_prs(self, repo, max_age_days: int) -> list[RawDocument]:
        """Crawl merged PRs — body contains architectural context."""
        docs = []
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
        
        for pr in repo.get_pulls(state='closed', sort='updated', direction='desc'):
            if pr.merged_at and pr.merged_at < cutoff_date:
                break  # PRs are sorted by updated, stop when too old
            
            if not pr.merged_at or not pr.body:
                continue  # Skip unmerged or empty PRs
            
            content = f"# PR #{pr.number}: {pr.title}\n\n{pr.body}"
            
            docs.append(RawDocument(
                uri=f"github://pr/{repo.full_name}/{pr.number}",
                source_type="github",
                title=f"PR #{pr.number}: {pr.title}",
                content=content,
                content_hash=sha256(content.encode()).hexdigest(),
                created_at=pr.created_at,
                updated_at=pr.merged_at,
                author_ids=[pr.user.login],
                space_id=repo.full_name,
                parent_ids=[],
                tags=pr.labels and [l.name for l in pr.labels] or [],
                raw_metadata={
                    "pr_number": pr.number,
                    "merged_at": pr.merged_at.isoformat(),
                    "base_branch": pr.base.ref,
                    "changed_files": pr.changed_files
                }
            ))
        
        return docs
    
    def _file_to_document(
        self, 
        content_file, 
        repo, 
        content_type: str
    ) -> RawDocument:
        raw_content = content_file.decoded_content.decode('utf-8', errors='replace')
        
        return RawDocument(
            uri=f"github://file/{repo.full_name}/{content_file.path}",
            source_type="github",
            title=f"{repo.name}/{content_file.path}",
            content=raw_content,
            content_hash=sha256(raw_content.encode()).hexdigest(),
            created_at=datetime.utcnow(),  # GitHub API doesn't provide file create date easily
            updated_at=datetime.utcnow(),
            author_ids=[],
            space_id=repo.full_name,
            parent_ids=[],
            tags=[content_type],
            raw_metadata={
                "repo": repo.full_name,
                "path": content_file.path,
                "sha": content_file.sha,
                "content_type": content_type
            }
        )
```

### GitHub Webhooks (Real-Time Updates)

```python
# src/integrations/github/webhooks.py
# Register webhook at: https://github.com/org/repo/settings/hooks

@router.post("/webhooks/github")
async def github_webhook(request: Request):
    # Verify signature
    signature = request.headers.get('X-Hub-Signature-256')
    body = await request.body()
    verify_github_signature(body, signature, settings.GITHUB_WEBHOOK_SECRET)
    
    payload = await request.json()
    event_type = request.headers.get('X-GitHub-Event')
    
    if event_type == 'push':
        # Triggered on any push to main — re-index changed files
        for commit in payload['commits']:
            for file_path in commit['modified'] + commit['added']:
                if file_path.endswith('.md') or 'docs/' in file_path:
                    await reindex_queue.add(GitHubFileReindexTask(
                        repo=payload['repository']['full_name'],
                        file_path=file_path,
                        commit_sha=payload['after']
                    ))
    
    elif event_type == 'pull_request':
        if payload['action'] == 'closed' and payload['pull_request']['merged']:
            # New merged PR → index it
            await reindex_queue.add(GitHubPRIndexTask(
                repo=payload['repository']['full_name'],
                pr_number=payload['number']
            ))
    
    elif event_type == 'release':
        # New release → trigger Dependency Tracker check
        await dep_tracker.check_on_release(
            repo=payload['repository']['full_name'],
            tag=payload['release']['tag_name'],
            release_notes=payload['release']['body']
        )
    
    return {"status": "ok"}
```

### GitHub-Specific Limitations

```
⚠️  Private repos: The GitHub token must have `repo` scope to access private repos.
    Use GitHub App with specific repository access rather than broad PAT.

⚠️  Large repos: Repos with 10k+ files are crawled selectively (README + /docs only).
    Configure GITHUB_MAX_REPO_SIZE_MB to skip oversized repos.

⚠️  Code indexing: Source code files (.py, .ts, .go, etc.) are NOT indexed by default.
    Only documentation files (.md, .rst, .txt) and structured comments are indexed.
    Enabling code indexing requires explicit opt-in per repo — it significantly
    increases index size and reduces retrieval precision.

⚠️  Rate limits: GitHub API = 5000 requests/hour (authenticated).
    GitHub App = 15000 requests/hour per installation.
    Crawler uses conditional requests (ETags) to minimise rate limit consumption.
```

---

## 5. Secondary Integrations (Jira, PDF, URL)

### Jira Integration

```python
# Auth: Jira REST API + API token
from atlassian import Jira

jira = Jira(
    url=settings.JIRA_URL,
    username=settings.JIRA_EMAIL,
    password=settings.JIRA_API_TOKEN,
    cloud=True
)

# Index: issue summaries + descriptions + comments
# Filter: closed/resolved issues only (open issues are too unstable)
# Max age: 12 months (configurable)
# Key insight: Jira issues = resolved institutional knowledge
#   "How we fixed the Kafka consumer lag in Q2" lives in a closed Jira issue
```

### PDF Upload

```python
# Endpoint: POST /api/ingest/pdf
# Max file size: 50MB (configurable)
# Processing: Docling for extraction, then standard ingestion pipeline

@router.post("/api/ingest/pdf")
async def ingest_pdf(
    file: UploadFile = File(...),
    access_level: str = Form("team"),  # "public" | "team:<id>" | "restricted:<id>"
    user: User = Depends(get_current_user)
):
    content = await file.read()
    doc = await docling_parser.parse_pdf(content, filename=file.filename)
    doc.metadata.rbac_level = access_level
    doc.metadata.uploaded_by = user.id
    
    task_id = await ingest_pipeline.run_async(doc)
    return {"task_id": task_id, "status": "queued"}
```

### URL Ingestion (On-Demand)

```python
# Triggered by T3 Live Doc Agent or explicit user submission
# Two methods:
# 1. Firecrawl: for JS-rendered docs (React/Next.js documentation sites)
# 2. requests + BeautifulSoup: fallback for static pages

async def ingest_url(url: str, ephemeral: bool = True) -> list[Chunk]:
    try:
        # Try Firecrawl first (handles JS-rendered)
        result = firecrawl.scrape_url(url, params={'formats': ['markdown']})
        content = result['markdown']
    except Exception:
        # Fallback to requests
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.text, 'html.parser')
        # Remove nav, footer, ads
        for tag in soup.find_all(['nav', 'footer', 'aside', 'script', 'style']):
            tag.decompose()
        content = markdownify.markdownify(str(soup.body))
    
    if ephemeral:
        # Session-scoped storage (T3 Live Doc Agent)
        return await ephemeral_store.add(content, source=url)
    else:
        # Permanent ingest (user explicitly added external doc)
        doc = RawDocument(uri=url, source_type="url", content=content, ...)
        return await ingest_pipeline.run(doc)
```

---

## 6. RBAC Enforcement Across Sources

RBAC is enforced at the retrieval layer — not at the UI layer. This means a user cannot retrieve a chunk they don't have access to, even via API.

```python
# Every chunk in Qdrant has an rbac_level payload field
# Every query filters by the user's accessible levels

def build_rbac_filter(user: User) -> Filter:
    accessible_levels = ["public"]
    
    if user.role in ["employee", "manager", "head"]:
        accessible_levels.append(f"team:{user.team_id}")
    
    if user.role in ["manager", "head"]:
        # Managers can see their reports' team content
        report_teams = get_report_teams(user.team_id)
        accessible_levels.extend([f"team:{t}" for t in report_teams])
    
    if user.role == "head":
        # Heads see everything except user-private content
        accessible_levels.append("org")
    
    return Filter(
        must=[
            FieldCondition(
                key="rbac_level",
                match=MatchAny(any=accessible_levels)
            )
        ]
    )

# Applied at query time:
results = qdrant_client.search(
    collection_name="enterprise_kb",
    query_vector=query_embedding,
    query_filter=build_rbac_filter(current_user),
    limit=50
)
```

### Source-to-RBAC Mapping

| Source | Default RBAC Level | Override |
|---|---|---|
| Notion page (shared with integration) | `team:<space_owner_team>` | Set per-page via Notion tags |
| Confluence page (team space) | `team:<space_key_mapped_team>` | Set per-space in config |
| Confluence page (personal space) | `restricted:<user_id>` | Not indexable by default |
| GitHub README / docs | `public` (if public repo) or `team:<repo_team>` | Set per-repo in config |
| GitHub PR | `team:<repo_team>` | Non-configurable |
| Jira issue | `team:<project_team>` | Non-configurable |
| PDF upload | Set by uploader at upload time | Manager can override |

---

## 7. Change Detection & Re-indexing

```python
# src/ingestion/change_detector.py

async def check_for_changes(source_type: str, space_id: str):
    """
    Compare current content hashes with stored hashes.
    Queue changed documents for re-indexing.
    """
    stored_hashes = await doc_store.get_all_hashes(source_type, space_id)
    
    if source_type == "notion":
        current_docs = await notion_crawler.crawl_workspace(space_id)
    elif source_type == "confluence":
        current_docs = await confluence_crawler.crawl_space(space_id)
    elif source_type == "github":
        current_docs = await github_crawler.crawl_repo(space_id)
    
    for doc in current_docs:
        stored_hash = stored_hashes.get(doc.uri)
        
        if stored_hash is None:
            # New document
            await ingest_queue.add(IngestTask(doc=doc, reason="new"))
        
        elif stored_hash != doc.content_hash:
            # Changed document
            await ingest_queue.add(IngestTask(doc=doc, reason="updated"))
            
            # Check if any existing answers cited this document
            # (Area 5 Provenance Graph — when implemented)
            await answer_invalidation_checker.check(doc.uri)

# Schedule:
# Notion: every 30 minutes (Notion has near-real-time updates)
# Confluence: every 60 minutes
# GitHub: webhook-driven (see Section 4) + hourly fallback
# Jira: every 60 minutes (closed issues only)
```

---

## 8. Full Tech Stack Reference

### Core AI/ML

| Component | Technology | Version | License | Notes |
|---|---|---|---|---|
| LLM Primary | Claude Sonnet-4 | Latest | Commercial | Answer synthesis, 200k context |
| LLM Fast | Claude Haiku | Latest | Commercial | Guardrails, CAG, classification |
| LLM Alt Primary | Gemini 1.5 Pro | Latest | Commercial | Alternative if using GCP credits |
| Embeddings | `BAAI/bge-m3` | Latest | MIT | Dense + sparse in one pass |
| Reranker | `BAAI/bge-reranker-v2-m3` | Latest | Apache 2.0 | Cross-encoder, multilingual |
| PII / NER | `urchade/gliner_medium-v2.1` | Latest | Apache 2.0 | Local inference, zero egress |
| Query Classification | Claude Haiku | Latest | Commercial | Fast + cheap |

### Storage

| Component | Technology | Version | Notes |
|---|---|---|---|
| Vector DB | Qdrant | 1.9+ | Multi-vector native, Docker deployable |
| Vector DB (dev) | ChromaDB | 0.5+ | Local dev only, not for production |
| Relational DB | PostgreSQL | 16 | Interaction log, page index, metadata |
| Cache | Redis | 7.2 | CAG context store, session state |
| Graph DB | Neo4j | 5.x | Area 5 knowledge graph (planned) |
| Graph DB (dev) | NetworkX | 3.x | In-memory, local dev only |

### Ingestion & Processing

| Component | Technology | Notes |
|---|---|---|
| Doc parsing | Docling | PDF, HTML, markdown, code — semantic chunking |
| Sparse retrieval | `rank-bm25` | Zero infra, exact token matching |
| Code parsing | `tree-sitter` | AST-level diff for Dependency Tracker |
| Code search | `ripgrep` | Fast codebase impact scan |
| HTML/web parsing | `BeautifulSoup4` + `markdownify` | Fallback for static pages |
| Live scraping | Firecrawl SDK | JS-rendered documentation sites |
| Web search | Tavily Python SDK | Multi-source search fallback |

### Application Layer

| Component | Technology | Notes |
|---|---|---|
| Agent orchestration | LangGraph | Stateful multi-agent graph, ReAct |
| API framework | FastAPI | REST API, async |
| Frontend | React + Tailwind | Chat UI with citation cards |
| Task queue | Celery + Redis | Async ingestion and nightly jobs |
| Scheduler | Celery Beat | Nightly CAG, incremental sync, anomaly checks |
| HTTP client | `httpx` | Async HTTP for all integrations |

### Integrations

| Source | SDK / Method | Auth |
|---|---|---|
| Notion | `notion-client` Python SDK | Integration token |
| Confluence | `atlassian-python-api` | API token (basic auth) |
| GitHub | `PyGithub` + webhooks | GitHub App or PAT |
| Jira | `atlassian-python-api` | API token |
| SharePoint (optional) | Microsoft Graph API | OAuth 2.0 |
| Google Docs (optional) | Google Drive API v3 | OAuth 2.0 / Service account |

---

## 9. Local Development Setup

```bash
# Prerequisites: Docker, Docker Compose, Python 3.12, Node 20

# 1. Clone and setup
git clone https://github.com/your-org/enterprise-knowledge-copilot
cd enterprise-knowledge-copilot
cp .env.example .env  # Fill in API keys

# 2. Start infrastructure
docker-compose up -d qdrant postgres redis

# 3. Install Python dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt --break-system-packages

# 4. Run database migrations
alembic upgrade head

# 5. Download models (one-time, ~2GB)
python scripts/download_models.py
# Downloads: BAAI/bge-m3, BAAI/bge-reranker-v2-m3, urchade/gliner_medium-v2.1

# 6. Run initial ingest (demo data)
python scripts/seed_demo_data.py  # Loads k8s + FastAPI docs for demo

# 7. Start the API
uvicorn src.api.main:app --reload --port 8000

# 8. Start the frontend (separate terminal)
cd frontend && npm install && npm run dev

# 9. Start Celery worker (separate terminal)
celery -A src.tasks worker --loglevel=info

# 10. Start Celery Beat scheduler (separate terminal)
celery -A src.tasks beat --loglevel=info
```

### Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage

  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: ekc_db
      POSTGRES_USER: ekc_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7.2-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  qdrant_data:
  postgres_data:
  redis_data:
```

---

## 10. Environment Variables

```bash
# .env.example

# LLM
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_AI_API_KEY=...           # Gemini alternative

# Integrations
NOTION_INTEGRATION_TOKEN=secret_...
CONFLUENCE_URL=https://yourcompany.atlassian.net
CONFLUENCE_EMAIL=bot@yourcompany.com
CONFLUENCE_API_TOKEN=...
GITHUB_TOKEN=ghp_...            # PAT or GitHub App token
GITHUB_WEBHOOK_SECRET=...
JIRA_URL=https://yourcompany.atlassian.net
JIRA_EMAIL=bot@yourcompany.com
JIRA_API_TOKEN=...

# Live scraping
FIRECRAWL_API_KEY=fc-...
TAVILY_API_KEY=tvly-...

# Infrastructure
DATABASE_URL=postgresql://ekc_user:${POSTGRES_PASSWORD}@localhost:5432/ekc_db
REDIS_URL=redis://localhost:6379/0
QDRANT_HOST=localhost
QDRANT_PORT=6333

# App
SECRET_KEY=...                  # JWT signing key
ENVIRONMENT=development         # development | staging | production

# Confluence spaces to index (comma-separated space keys)
CONFLUENCE_SPACES=ENG,PROD,OPS,DEVOPS

# GitHub repos to index (comma-separated org/repo format)
GITHUB_REPOS=myorg/backend-api,myorg/frontend,myorg/infra

# Notion workspaces (comma-separated workspace IDs)
NOTION_WORKSPACES=workspace_id_1,workspace_id_2

# Dependency Tracker
GITHUB_REPOS_TO_MONITOR=kubernetes/kubernetes,tiangolo/fastapi,apache/kafka

# Feature flags
ENABLE_DEPENDENCY_TRACKER=true
ENABLE_CAG_PIPELINE=true
ENABLE_PROACTIVE_ALERTS=true
ENABLE_KNOWLEDGE_GRAPH=false    # Area 5 — disabled until planned extension
```

---

*Previous: [03_analytics_and_intelligence.md](./03_analytics_and_intelligence.md)*
*Next: [05_market_strategy_and_gtm.md](./05_market_strategy_and_gtm.md)*
