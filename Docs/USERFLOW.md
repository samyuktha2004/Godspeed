# User Flows & Interface Specifications

> **Document purpose:** Define user journeys for each user role (Engineer, Manager, Admin) and the associated UI flows. Specifies what screens each role sees, when, and under what conditions.

---

## Table of Contents

1. [User Roles & Personas](#user-roles--personas)
2. [Engineer User Flow (Primary)](#engineer-user-flow-primary)
3. [New Hire / Intern / Apprentice User Flow](#new-hire--intern--apprentice-user-flow)
4. [Manager User Flow (Analytics)](#manager-user-flow-analytics)
5. [Admin User Flow (Configuration)](#admin-user-flow-configuration)
6. [Cross-Role Features](#cross-role-features)
7. [Real-Time Features](#real-time-features)
8. [Error Handling & Edge Cases](#error-handling--edge-cases)

---

## User Roles & Personas

### Role 1: Engineer (70% of users)

**What they do:** Query the knowledge base when stuck, discovering internal best practices, external API docs, and SOP runbooks.

**Key Pain Points:**
- Don't know where to look when debugging
- Need fast, cited answers (trust the source)
- Need context links to follow up
- Want to see related questions others asked

**Permissions:**
- Query all knowledge bases (subject to RBAC)
- View query analytics (personal + team trends)
- Leave feedback on answer quality
- Create queries against private docs (if RBAC-permitted)

---

### Role 2: Manager (20% of users)

**What they do:** Monitor team productivity, knowledge gaps, and query trends. Use dashboards to identify where training is needed.

**Key Pain Points:**
- Where are knowledge gaps in my team?
- Are people finding answers or going through escalations?
- What external dependencies are breaking?
- Is the knowledge base being used effectively?

**Permissions:**
- View aggregated team analytics (not individual engineers' queries)
- View knowledge health dashboard
- See escalation trends and hotspots
- Export reports for executives

---

### Role 2b: New Hire / Intern / Apprentice (subset of Engineer role)

**Who they are:** Developers who are new to the company — this includes full-time new hires in their first 1–4 weeks, summer interns, and apprentices on structured programmes. They hold the Engineer role in the system but their UX is differentiated because they have no query history, no familiarity with the team's terminology, and often don't know what questions to ask yet.

**Key Pain Points:**
- Don't know what they don't know — can't form good search queries yet
- Overwhelmed by the number of tools, repos, and processes
- Afraid to "bother" senior engineers with basic questions
- Don't know which team owns which service
- Need to read a lot of docs fast in their first week

**Permissions:** Same as Engineer (RBAC-filtered to their assigned team)

**Differentiated UX triggers:**
- Account is flagged `is_new_hire: true` (cleared after 30 days or manually by manager)
- Zero query history in the system (auto-detects first-time state)

---

### Role 3: Admin (5% of users)

**What they do:** Configure data sources, manage users, monitor system health, update RBAC policies.

**Key Pain Points:**
- Need to connect new data sources quickly
- Need to manage who can see what
- Need visibility into system usage and errors

**Permissions:**
- Full read/write on all data sources
- User management (invite, revoke, assign teams/roles)
- RBAC policy editor
- System health and usage dashboards
- API key management

---

## Engineer User Flow (Primary)

### Flow 1a: First-Time Engineer (Onboarded)

```
Entry Point: Visit app.godspeed.local/ after SSO login
    │
    ▼
[Dashboard - Home Page]
├─ Welcome banner ("Quick start guide")
├─ 3-step onboarding tour (if first visit)
│  └─ "Try asking something" → Launch query modal
├─ Suggested queries (trending this week)
├─ Recent queries (empty on first visit)
└─ Quick links to Help + Admin contact
    │
    ▼ [User clicks "Try a query" or goes to Search]
    │
[Query Modal / Search Interface]
├─ Large search box with placeholder: "Ask anything (e.g., 'How do I set up a PostgreSQL connection?')"
├─ Suggested entities (recent team searches, trending topics)
└─ [CTRL+K search shortcut enabled globally]
    │
    ▼ [User types query + hits Enter]
    │
[Results Page - Progressive Rendering]
├─ Search bar (reusable, with clear button)
├─ Loading skeleton (shown ONLY until the first event from either stream arrives):
│  └─ Single pulsing skeleton placeholder — disappears the moment first data lands
│     (first SSE event from /agent/query  OR  first node from /graph/stream)
│     Condition: if ANY data has arrived, show it — never switch back to skeleton
├─ Once first event arrives, populate in-place without page switch or reload:
│  ├─ Answer area: tokens stream in word-by-word as SSE answer_chunk events arrive
│  ├─ Knowledge graph canvas: nodes appear one-by-one as WS node events arrive
│  │   (graph starts rendering from the first node — no wait for full graph)
│  ├─ Related documents: populated after agent_done events complete
│  └─ Query suggestions: appended last, after done event fires
├─ For each result chunk:
│  ├─ Title + source badge (Notion / Confluence / GitHub / PDF / URL)
│  ├─ Last updated timestamp (e.g., "Updated 2 days ago")
│  ├─ Relevance score (0-100, hidden by default, toggle-visible for power users)
│  └─ "Open source" link (opens in new tab)
├─ Follow-up prompt: "Ask a follow-up or try a new search"
└─ Feedback buttons: [Thumbs up] [Thumbs down] [Report outdated]
    │
    ▼ [Optional: User clicks knowledge graph node]
    │
[Knowledge Graph Node Detail]
├─ Entity name + type (e.g., "PostgreSQL Connection Pool")
├─ Related entities (connected nodes, clickable)
├─ All documents mentioning this entity
└─ Back button to results
    │
    ▼ [Optional: User clicks "Save to workspace"]
    │
[Workspace View]
├─ Personal workspace (can save queries/results for later)
├─ Shareable with team
└─ Can export to Markdown/PDF
```

### Flow 1b: Follow-Up Query

```
[Results Page]
    │
    ▼ [User types in "Ask a follow-up" box]
    │
[Results Update]
├─ Previous answer stays visible (scrollable)
├─ New answer appends below with "Follow-up #1" label
├─ Same progressive loading as initial query
└─ Full conversation history visible
    │
    ▼ [User can branch to new search]
    │
[New Query from Results]
├─ Search box at top resets
├─ Previous conversation persists in sidebar
└─ Option to "Return to previous conversation" (breadcrumb)
```

### Flow 1c: Query History & Saved Searches

```
Entry Point: Sidebar > "Query History" or Cmd+Shift+H
    │
    ▼
[Query History Page]
├─ List of past 100 queries (most recent first)
├─ Filters:
│  ├─ Date range
│  ├─ Team filter (if multi-team)
│  ├─ Source filter (Notion, Confluence, etc.)
│  ├─ Sentiment (helpful, not helpful, neutral)
│  └─ Search within history
├─ Each item shows:
│  ├─ Query text (truncated, expandable)
│  ├─ Timestamp
│  ├─ Your feedback (thumbs up/down if given)
│  ├─ [Re-run] button
│  └─ [Save to workspace] button (star icon)
└─ Pagination (20 per page)
    │
    ▼ [User clicks a past query]
    │
[Re-run Query]
├─ Load previous conversation with updated answer
├─ Highlight what changed since last run
└─ Option to branch to follow-up
```

---

## New Hire / Intern / Apprentice User Flow

> These flows apply when `is_new_hire: true` OR the account has zero query history. The system detects first-time state automatically and downgrades the experience to guided mode. It never assumes prior familiarity with the team's codebase, terminology, or processes.

### Flow 4a: Day-One Onboarding (First Login)

```
Entry Point: Invitation email → "Activate account" link → First login
    │
    ▼
[Account Activation]
├─ Set password (or SSO — OIDC if configured)
├─ Choose display name
└─ Team auto-assigned by admin at invite time
    │
    ▼
[Welcome Screen — Onboarding Mode]
├─ Header: "Welcome to Godspeed, [Name] 👋"
├─ Subtitle: "Your team's knowledge base. Ask anything, get cited answers."
├─ Team context card:
│  ├─ "You've joined: [Backend Team]"
│  ├─ "Your team works with: [Service list from team's Neo4j nodes]"
│  └─ "Common topics your teammates ask about: [top 5 query topics for this team]"
├─ [Start guided tour — 3 steps] (dismissible)
└─ [Skip to search]
    │
    ▼ [User clicks "Start guided tour"]
    │
[Step 1 of 3: What this is]
├─ Overlay on search box:
│  "Ask any engineering question — about our codebase, runbooks, incidents, or docs."
│  Example: "How does the auth service handle token expiry?"
└─ [Next →]
    │
    ▼
[Step 2 of 3: How answers work]
├─ Overlay on a sample result:
│  "Every answer shows exactly which document it came from.
│   If you're unsure, click the citation to read the source."
└─ [Next →]
    │
    ▼
[Step 3 of 3: The knowledge graph]
├─ Overlay on graph canvas:
│  "This shows how services, libraries, and incidents connect.
│   Click any node to explore related docs."
└─ [Done — start searching]
    │
    ▼
[Onboarding Dashboard — Home Page in New-Hire Mode]
├─ Starter Pack panel (replaces trending queries):
│  ├─ "Get started with questions your team asks in week 1:"
│  ├─ [ ] How do I set up my local dev environment?
│  ├─ [ ] What services does [team name] own?
│  ├─ [ ] Where are the runbooks for on-call?
│  ├─ [ ] How does deployment work here?
│  └─ [ ] Who do I contact for access to [X]?
│     (Clicking any of these fires it as a real query)
├─ Your mentor: [Name, assigned by manager] — "[Message]" button
├─ Useful links (admin-configured per team):
│  ├─ Team Confluence space
│  ├─ On-call runbook
│  └─ Engineering handbook
└─ Progress tracker: "You've asked [0] questions this week"
```

### Flow 4b: First Query (New Hire Context)

```
[Home or Search]
    │
    ▼ [User types first query — possibly vague or misspelled]
    │
[Query Processing]
├─ Same SSE/streaming backend as standard Engineer flow
├─ If query is very short (< 3 words) AND is_new_hire:
│  └─ Frontend appends context hint below search box:
│     "💡 Try being more specific, e.g. 'How does X work in our codebase?'"
│     (Non-blocking — query still fires)
    │
    ▼ [Results Page — New-Hire augmentation]
    │
[Results — New Hire Extras]
├─ Standard progressive rendering (same as Engineer flow)
├─ After answer loads: "New to this topic?" expandable card:
│  ├─ "Related starter questions:"
│  ├─ [Suggested follow-up 1]  [Suggested follow-up 2]
│  └─ "Ask your mentor: [Name]"
├─ If answer has guardrail_result.escalate=true:
│  └─ Banner: "This is a complex topic — consider asking [mentor name] directly."
│     (Escalation banner personalised with mentor name for new hires)
└─ Standard feedback buttons (thumbs up/down)
    │
    ▼ [Optional: User clicks "Ask your mentor"]
    │
[Mentor Nudge]
├─ Pre-filled message: "I asked Godspeed about '[query text]' — can you help me understand it better?"
└─ Opens in whatever comms tool is configured (Slack deep link / mailto fallback)
```

### Flow 4c: Onboarding Progress (First Two Weeks)

```
[Home Page — New-Hire Mode, days 1–14]
    │
├─ Progress tracker updates after each query:
│  ├─ Week 1 goal: "Ask 10 questions" → [████░░░░░░] 4/10
│  ├─ Topics explored: [Auth] [Deployments] [Databases] (badges)
│  └─ "You've saved 2h of context-switching this week" (derived from query count × avg resolution time)
│
├─ Weekly digest (sent at end of week 1):
│  ├─ "Here's what you learned this week"
│  ├─ Top 5 queries + answers (bookmarked automatically if marked helpful)
│  └─ "Topics your team is discussing right now" (live from team query trends)
│
└─ [Dismiss new-hire mode] button (available from day 3 onward)
   └─ Or auto-dismissed after 30 days / manager marks "onboarding complete"
```

### Flow 4d: Intern-Specific (Time-Bounded Account)

```
[Settings > Account]
├─ "Intern account — active until [date]"
├─ Exports available before account expires:
│  ├─ [Download my query history]
│  ├─ [Export saved workspace to PDF]
│  └─ [Email me a copy]
├─ 7 days before expiry:
│  └─ Banner: "Your account expires in 7 days. Export your work."
└─ On expiry: account deactivated (data retained for 90 days for compliance)
```

### Flow 4e: Manager View of New Hire (How Managers See This)

```
[Analytics Dashboard] > [Team] > [New Hires tab]
    │
    ▼
[New Hire Overview]
├─ List of active new hires / interns on this team:
│  ├─ Name | Start date | Queries asked | Topics explored | Last active
│  ├─ Alice (intern) | Week 2 | 14 queries | Auth, Deploy | 2h ago
│  └─ Bob (new hire) | Week 1 | 3 queries | — | Yesterday
│
├─ Knowledge gap indicator per new hire:
│  └─ Topics asked about 3+ times with low satisfaction = "needs support"
│
├─ Manager actions:
│  ├─ [Mark onboarding complete] — removes new-hire mode
│  ├─ [Assign/change mentor]
│  └─ [Add starter pack question] — curate team-specific onboarding queries
│
└─ Aggregate: "Average queries before first productive week: [X]"
   (Benchmark: helps managers see if new hires are self-serving or escalating too early)
```

---

## Manager User Flow (Analytics)

### Flow 2a: First-Time Manager Login

```
Entry Point: app.godspeed.local/analytics (role-based redirect)
    │
    ▼
[Analytics Dashboard - Welcome]
├─ Onboarding: "Your team's knowledge dashboard"
├─ High-level metrics:
│  ├─ Queries answered this week: [1,243]
│  ├─ Escalations prevented: [342]
│  ├─ Knowledge gaps identified: [8]
│  └─ Team learning time saved: [120 hours]
├─ Visual: 4 KPI cards with trend sparklines (↑ 12% vs last week)
├─ CTA: "View detailed reports" or "Configure team settings"
└─ Left sidebar: Navigation to sub-dashboards
```

### Flow 2b: Query Analytics

```
[Analytics Dashboard] > [Query Analytics]
    │
    ▼
[Query Analytics Page]
├─ Filters:
│  ├─ Date range (default: last 30 days)
│  ├─ Team (if admin with multi-team access)
│  └─ Metrics type (usage, performance, quality)
├─ Charts:
│  ├─ Query volume trend (line chart, 30-day daily)
│  ├─ Top 10 query topics (bar chart, auto-clustered)
│  ├─ Query success rate (gauge, colored: green ≥80%, yellow ≥60%, red <60%)
│  ├─ Top data sources used (pie chart: Notion, Confluence, GitHub, etc.)
│  └─ Response time distribution (box plot: P50, P75, P95)
├─ Table: Recent queries (sortable, filterable)
│  ├─ Query text | Asker | Timestamp | Sentiment | Source used
│  └─ Can drill down into individual query
├─ Export buttons: [CSV] [PDF Report]
└─ Drill-down: Click on a topic to see all related queries
```

### Flow 2c: Knowledge Health Dashboard

```
[Analytics Dashboard] > [Knowledge Health]
    │
    ▼
[Knowledge Health Page]
├─ Overall score: "7.2 / 10" with trend indicator
├─ Breakdown:
│  ├─ Coverage (% of engineering topics with docs): 68% (↑ from 65%)
│  ├─ Freshness (% docs updated <90 days): 82% (↓ from 85%)
│  ├─ Accuracy (% queries with 4+ star feedback): 76%
│  └─ Accessibility (% queries resolved without escalation): 71%
├─ Knowledge gap heatmap:
│  ├─ Y-axis: Topics (Databases, DevOps, Frontend, Backend, etc.)
│  ├─ X-axis: Last updated time (red = stale, yellow = needs review, green = current)
│  └─ Clickable cells show docs in that category
├─ Top escalations (queries that went unresolved):
│  ├─ "How to debug OOM errors in Rust" — asked 12 times, 0 helpful answers
│  ├─ "Netflix API deprecation timeline" — asked 8 times, docs outdated
│  └─ CTA: "Create runbook" or "Update docs"
├─ Recommendations:
│  ├─ "Your Jira integration hasn't synced in 3 days"
│  ├─ "PostgreSQL docs are 180 days stale; recommend refresh"
│  └─ "High query volume on 'GraphQL best practices' but no in-house docs"
└─ Action buttons: [Sync data sources] [Request documentation] [Contact team lead]
```

### Flow 2d: Dependency Tracker

```
[Analytics Dashboard] > [Dependencies]
    │
    ▼
[Dependency Tracker Page]
├─ Alert banner: "3 breaking changes in dependencies used by your team"
├─ Table: Dependencies your team uses
│  ├─ Dependency | Current version | Latest version | Breaking changes | Impact
│  ├─ PostgreSQL | 14.2 | 15.3 | Yes (migration guide) | HIGH
│  ├─ Node.js | 18.12 | 20.x | No | LOW
│  └─ React | 18.2 | 19 beta | Yes (API changes) | MEDIUM
├─ Each row with:
│  ├─ [View changelog] link
│  ├─ [Request patch PR] button
│  └─ [Dismiss for 30 days] option
├─ Historical view: "Breaking changes this month"
│  ├─ Timeline of changes that affected team
│  └─ Link to fixes already applied
├─ Export: [Share breaking changes digest with team]
└─ Proactive notifications: Enabled/disabled per dependency
```

### Flow 2e: Team Settings (Manager)

```
[Analytics Dashboard] > [Team Settings]
    │
    ▼
[Team Settings Page]
├─ Team info:
│  ├─ Team name
│  ├─ Members: [+Add] [Manage roles]
│  └─ Knowledge sources assigned to team (Notion workspace, Confluence space, etc.)
├─ Data source permissions:
│  ├─ Which Confluence spaces this team can access
│  ├─ Which GitHub repos
│  ├─ Which Notion workspaces
│  └─ [Edit access]
├─ Analytics preferences:
│  ├─ Alert me if query success rate drops below [   ]%
│  ├─ Notify on new escalations
│  ├─ Weekly digest: [Enabled]
│  └─ Report recipients: [+Add email]
├─ Export/backup:
│  ├─ [Download team analytics]
│  └─ [Export knowledge base]
└─ Danger zone: [Archive team] [Delete team]
```

---

## Admin User Flow (Configuration)

### Flow 3a: Admin Dashboard Home

```
Entry Point: app.godspeed.local/admin (role-based redirect)
    │
    ▼
[Admin Dashboard - Overview]
├─ System health:
│  ├─ Backend: [✓ Healthy] (uptime 99.97%)
│  ├─ Database: [✓ Healthy] (response time p95: 45ms)
│  ├─ Vector DB: [✓ Healthy] (index size: 2.3GB)
│  ├─ Redis: [✓ Healthy] (cache hit rate: 78%)
│  └─ Last checked: [2 minutes ago] [Manual refresh]
├─ Usage metrics:
│  ├─ Active users this month: 1,243
│  ├─ Queries processed: 45,678
│  ├─ Credit usage: 78% (warning color if near limit)
│  └─ Storage used: 15.3GB / 100GB
├─ Alerts:
│  ├─ [⚠] Notion integration is stale (last sync 6 hours ago, usually hourly)
│  ├─ [⚠] Jira webhook failed 3 times in last hour
│  ├─ [✓] All other integrations nominal
├─ Left sidebar navigation:
│  ├─ Dashboard (home)
│  ├─ Data Sources
│  ├─ User Management
│  ├─ RBAC Policies
│  ├─ API Keys
│  ├─ System Settings
│  ├─ Logs & Monitoring
│  └─ Billing (if multi-tenant)
└─ Quick actions: [Restart sync] [Clear cache] [Run health check]
```

### Flow 3b: Data Source Management

```
[Admin Dashboard] > [Data Sources]
    │
    ▼
[Data Sources Page]
├─ List of connected data sources:
│  ├─ Source | Type | Status | Last sync | Records | [Actions]
│  ├─ "Engineering Confluence" | Confluence | ✓ Active | 2 min ago | 4,231 docs | [Edit] [Test] [Manual sync] [Disconnect]
│  ├─ "GitHub Repos" | GitHub | ✓ Active | 5 min ago | 891 PRs | [Edit] [Test] [Manual sync] [Disconnect]
│  ├─ "Notion Workspace" | Notion | ⚠ Stale | 6 hours ago | 2,104 docs | [Edit] [Reconnect] [Manual sync] [Troubleshoot]
│  └─ "PDF Library" | Upload | ✓ Active | — | 156 files | [Edit] [Remove] [Bulk upload]
├─ [+ Add new source] button
└─ Bulk actions: [Enable all] [Disable all] [Sync all now]
    │
    ▼ [User clicks "+ Add new source"]
    │
[Add Data Source Wizard]
├─ Step 1: Choose source type
│  ├─ [Notion] [Confluence] [GitHub] [Slack] [Jira] [PDF] [URL] [Other]
├─ Step 2: Authenticate (OAuth flow or API key)
│  ├─ "Click to authenticate with Notion"
│  └─ Redirects to Notion OAuth, returns token
├─ Step 3: Configure scope
│  ├─ For Notion: "Select workspaces to sync"
│  ├─ For GitHub: "Select repositories to sync"
│  ├─ For Confluence: "Select spaces to sync"
│  └─ Checkbox: "Automatically sync new spaces/repos"
├─ Step 4: Test connection
│  ├─ [Test] button
│  ├─ Shows: "✓ Connected successfully. Found 4,231 documents."
│  └─ [Back to adjust] [Save source]
├─ Step 5: Confirm & set RBAC
│  ├─ "Who can access docs from this source?"
│  ├─ [All teams] [Specific teams] [Specific users]
│  ├─ [+ Create team if needed]
│  └─ [Save & sync now] [Save & sync later]
├─ Step 6: Monitor sync job
│  ├─ Progress bar: "Syncing Notion workspace... 45% complete"
│  ├─ Real-time log of what's being fetched
│  └─ ETA: 3 minutes remaining
    │
    ▼ [Sync completes]
    │
[Sync Success]
├─ "✓ Successfully synced 4,231 documents"
├─ Summary: "4,100 new docs, 131 updated, 0 deleted"
├─ [Edit source again] [View newly added docs] [Done]
└─ Source appears in list with status ✓ Active
    │
    ▼ [Optional: Click on existing source to manage]
    │
[Edit Data Source]
├─ Name: "Engineering Confluence" [Edit]
├─ Type: Confluence (locked)
├─ Status: ✓ Active [Change to inactive]
├─ Last sync: 2 min ago [Manual sync now]
├─ Sync frequency: [Every 1 hour ▼]
├─ Scope: Spaces selected: [Engineering] [DevOps] [Product] [Change scope]
├─ RBAC: All teams [Change to specific teams]
├─ Advanced:
│  ├─ Auto-purge docs if they disappear from source: [Enabled]
│  ├─ Preserve modification history: [Enabled]
│  └─ PII masking level: [Standard ▼] (Standard / Strict / Disabled)
├─ Logs:
│  ├─ Sync history (last 10 syncs, clickable for details)
│  ├─ Error log (if any failures)
│  └─ [Download detailed log]
├─ Danger zone: [Disconnect source] [Re-authenticate] [Clear cached data]
└─ [Save changes] [Cancel]
```

### Flow 3c: User Management

```
[Admin Dashboard] > [User Management]
    │
    ▼
[User Management Page]
├─ List of all users:
│  ├─ User | Email | Role | Team | Status | [Actions]
│  ├─ Alice Chen | alice@company.com | Admin | — | Active | [View] [Edit] [Deactivate]
│  ├─ Bob Lee | bob@company.com | Engineer | Backend | Active | [View] [Edit] [Deactivate]
│  ├─ Carol Smith | carol@company.com | Manager | Frontend | Active | [View] [Edit] [Deactivate]
│  └─ David Brown | david@company.com | Engineer | DevOps | Invited | [View] [Resend invite] [Cancel]
├─ Filters: [Role ▼] [Team ▼] [Status ▼] [Search by name/email]
├─ Bulk actions: [Add to team] [Assign role] [Deactivate multiple]
└─ [+ Invite new user] button
    │
    ▼ [User clicks "+ Invite new user"]
    │
[Invite User Modal]
├─ Email address(es): [_______________________] [+ Add another]
├─ Role: [Engineer ▼]
├─ Team(s): [Backend ▼] [+ Add team]
├─ Permissions:
│  ├─ [✓] Query knowledge base
│  ├─ [✓] View personal analytics
│  ├─ [✓] Save queries to workspace
│  ├─ [ ] Manage data sources (only if Admin)
│  └─ [ ] Manage users (only if Admin)
├─ Invite message: [Optional message to include in email]
└─ [Send invitations] [Cancel]
    │
    ▼ [Invitation sent]
    │
[Confirmation]
├─ "✓ Invitation sent to alice@company.com"
├─ "She'll receive an email and need to activate her account"
└─ [Invite more] [Done]
```

### Flow 3d: RBAC Policy Editor

```
[Admin Dashboard] > [RBAC Policies]
    │
    ▼
[RBAC Policies Page]
├─ Current policies:
│  ├─ "Public knowledge (all teams)" — All docs from: [Public Confluence, GitHub README, URLs]
│  ├─ "Backend Team Only" — Docs tagged: [Notion workspace: Backend], [Confluence space: Backend]
│  ├─ "Restricted: CTO only" — Docs tagged: [Financial_Reports, Security_Audits]
│  └─ [Edit] [Delete] [Clone]
├─ [+ Create new policy] button
└─ Preview: How many docs match each policy
    │
    ▼ [User clicks "+ Create new policy"]
    │
[Create RBAC Policy]
├─ Policy name: [_________________]
├─ Description: [_________________]
├─ Who can access? (checkboxes):
│  ├─ [✓] All teams
│  ├─ [ ] Specific teams: [Backend ▼] [Frontend ▼] [+ Add]
│  ├─ [ ] Specific users: [alice@company.com] [bob@company.com] [+ Add]
├─ Which data sources? (checkboxes):
│  ├─ [✓] "Engineering Confluence"
│  ├─ [ ] "GitHub Repos"
│  ├─ [ ] "Notion Workspace"
│  ├─ [✓] "Public URLs"
├─ Additional filters:
│  ├─ Doc type: [Any ▼] or [SOP] [Runbook] [API_Doc] [PR] [etc.]
│  ├─ Min. age: [Any ▼] or [Docs updated in last 30 days]
│  └─ Tags: [Contains] [_______] [+ Add tag filter]
├─ Preview: "This policy will apply to [2,341] documents"
├─ Test access:
│  ├─ [Test as user: alice@company.com]
│  ├─ Result: "Alice would see 1,240 docs matching this policy"
│  └─ [Test as different user]
└─ [Save policy] [Save & preview] [Cancel]
```

### Flow 3e: API Key Management

```
[Admin Dashboard] > [API Keys]
    │
    ▼
[API Keys Page]
├─ List of active API keys:
│  ├─ Name | Created by | Created | Last used | Permissions | [Actions]
│  ├─ "CI/CD Pipeline" | alice@company.com | 3 months ago | 2 hours ago | Query, Ingest | [View] [Rotate] [Revoke]
│  ├─ "Mobile App" | bob@company.com | 1 month ago | 5 min ago | Query only | [View] [Rotate] [Revoke]
│  └─ "Third-party tool" | carol@company.com | 2 weeks ago | Never | Query, Webhook | [View] [Rotate] [Revoke]
├─ Inactive keys (older than 90 days without use):
│  ├─ "Old integration" | [Revoke] [Reactivate]
├─ [+ Create new API key] button
└─ Audit log: [View all key actions]
    │
    ▼ [User clicks "+ Create new API key"]
    │
[Create API Key]
├─ Name: [_________________] (e.g., "CI/CD Pipeline")
├─ Permissions (checkboxes):
│  ├─ [✓] Query knowledge base
│  ├─ [ ] Manage data sources
│  ├─ [ ] Manage RBAC
│  ├─ [ ] View analytics
│  ├─ [ ] Ingest documents
├─ Rate limits:
│  ├─ Queries per minute: [1000 ▼]
│  ├─ Ingestion jobs per day: [100 ▼]
├─ Expiry:
│  ├─ [No expiry] [Expire after: 90 days ▼]
├─ IP whitelist (optional):
│  ├─ [Optional] Restrict to IPs: [10.0.0.0/8] [+ Add CIDR]
└─ [Create key] [Cancel]
    │
    ▼ [Key created]
    │
[API Key Created]
├─ "✓ API key created successfully"
├─ Key: [sk-abc123def456... ▼] [Copy to clipboard]
├─ "⚠️ Save this key now. You won't see it again."
├─ Quick start:
│  ├─ [Show API docs]
│  ├─ [Show curl example]
│  ├─ [Show Python example]
└─ [Done]
```

---

## Cross-Role Features

### Feature: Feedback Loop

**Visible to:** Engineers, Managers, Admins

```
[Results Page / Answer]
    │
    ▼ [User clicks Thumbs Up / Thumbs Down]
    │
[Feedback Modal]
├─ "Was this answer helpful?"
├─ [Thumbs up] — "Yes, this solved my problem"
├─ [Thumbs down] — "No, this didn't help"
├─ Optional text: [Why? (optional feedback) ________________]
├─ [Submit] [Skip]
    │
    ▼ [Backend records feedback]
    │
[Thank you]
├─ "✓ Thanks for the feedback. We'll use this to improve."
└─ (closes modal)
```

**Backend flow:**
- Stores feedback with query ID, user ID, timestamp, sentiment, text
- Triggers: If downvote, suggest "Report outdated / hallucinated" option
- Manager sees: Aggregate feedback in query analytics dashboard
- Admin sees: Alert if downvote rate exceeds threshold (e.g., >20% for a topic)

---

### Feature: Share Results

**Visible to:** All roles

```
[Results Page]
    │
    ▼ [User clicks "Share" button]
    │
[Share Modal]
├─ Copy shareable link: [sk_abc123def456 ▼] [Copy]
├─ Shared with: [Anyone with link] [Specific team] [Specific users]
├─ Expires in: [Never] [7 days] [30 days]
├─ Include in shared link:
│  ├─ [✓] Generated answer
│  ├─ [✓] Citation sources
│  ├─ [ ] Knowledge graph
│  ├─ [ ] Feedback history
└─ [Generate link] [Copy] [Cancel]
```

---

### Feature: Workspace (Personal + Team)

**Visible to:** All roles (different permissions per role)

```
[Sidebar] > [Workspace] or [My Workspace]
    │
    ▼
[Workspace Page]
├─ Tabs: [Personal] [Team] [Shared with me]
├─ Personal workspace:
│  ├─ Saved queries (starred / favorited)
│  ├─ Saved result sets
│  ├─ Personal notes
│  └─ [+ Save current query] [+ Add note]
├─ Team workspace (if in a team):
│  ├─ Shared queries (manager-pinned)
│  ├─ Team runbooks
│  ├─ Recurring analyses
│  └─ [+ Share to team] (requires team lead approval or auto-approved per policy)
├─ Shared with me:
│  ├─ Queries/results shared by colleagues
│  ├─ [View] [Save to personal] [Comment]
└─ Export: [CSV] [Markdown] [PDF]
```

---

## Real-Time Features

### Feature: Live Notifications (WebSocket-driven)

**Visible to:** All roles (different event types per role)

```
[Top-right notification bell]
    │
    ▼ [New notification arrives via WebSocket]
    │
[Notification Toast]
├─ [Engineer]: "Query you asked last week now has an answer (new doc found)"
├─ [Manager]: "Team escalation spike detected (↑25%)"
├─ [Admin]: "Data source sync failed: Notion auth expired"
├─ Toast auto-dismisses in 5 seconds or [Dismiss] [View]
    │
    ▼ [User clicks "View" or bell icon]
    │
[Notification Center]
├─ Filter: [All] [Mentions] [System] [Tasks]
├─ List of notifications (most recent first):
│  ├─ [Bell icon] Query answered — "3 new docs about PostgreSQL connection pooling"
│  ├─ [Alert icon] Knowledge gap — "No docs found for 'WebSocket auth patterns' (5 queries this week)"
│  ├─ [Alert icon] Data sync failed — "Notion: auth expired"
│  ├─ [Team icon] Team mention — "@alice mentioned you in feedback on query #1234"
├─ Each notification shows:
│  ├─ Title
│  ├─ Time ago
│  ├─ [View] [Dismiss] [Snooze 24h]
└─ [Mark all as read]
```

**Notification types by role:**

| Event | Engineer | Manager | Admin |
|---|---|---|---|
| New docs match past query | ✓ Notify | — | — |
| Escalation detected | — | ✓ Notify | ✓ Notify |
| Knowledge gap found | ✓ Notify | ✓ Notify | ✓ Notify |
| Data source sync failed | — | — | ✓ Notify |
| Query you asked now has better answer | ✓ Notify | — | — |
| Team mentioned you in feedback | ✓ Notify | ✓ Notify | — |
| Breaking change in dependency | — | ✓ Notify | ✓ Notify |
| Credit warning | — | — | ✓ Notify |
| User invited to team | ✓ Notify (if team member) | — | ✓ Notify |

---

### Feature: Knowledge Graph (Progressive Streaming)

**Visible to:** All roles (different data per role)

**Architecture note:** Graph rendering is entirely in-page. The backend streams nodes/edges via WebSocket (`WS /graph/stream`). The frontend renders them with Force-Graph 2D as they arrive — no reload, no screen switch. Loading state only if zero data has arrived.

**Query-scoped subgraph (results page):** When a query is made, the frontend connects to `WS /graph/stream` scoped to the query's traversal — entities that are cited in the answer and their relationships. This uses `GET /graph/traverse?entity=...` seeded from the SSE-cited entities, not the full graph dump.

```
[Results Page] — Query submitted, two streams open simultaneously:
    │
    ├─ Stream 1: SSE POST /agent/query
    │  ├─ plan_ready → show agent names as badges (non-blocking)
    │  ├─ agent_started → highlight active agent badge
    │  ├─ answer_chunk → stream tokens into answer area word-by-word
    │  ├─ guardrail_result → show confidence badge
    │  └─ done → final answer complete, seed entity list for graph traverse
    │
    └─ Stream 2: WS /graph/stream (query-scoped)
       ├─ First node event → graph canvas appears, first node rendered
       ├─ Each subsequent node event → node added, animated
       ├─ Each edge event → edge drawn between existing nodes
       └─ done event → graph complete; show node/edge count
    │
    ▼ At no point does the page switch, reload, or blank out
    ├─ If first SSE event arrives before first WS node: answer renders, graph area shows subtle pulse
    ├─ If first WS node arrives: graph canvas activates immediately
    └─ Condition: skeleton ONLY if zero events from both streams
```

**Interaction:**
```
[User hovers over graph node]
    ├─ Tooltip: Entity name + type
    │
[User clicks graph node]
    ├─ Show side panel:
    │  ├─ Entity details
    │  ├─ All documents mentioning it
    │  ├─ Related entities
    │  └─ [View entity details] [Follow to new query]
    │
[User clicks graph edge]
    ├─ Highlight relationship
    └─ Show relationship type (e.g., "relates-to", "depends-on", "extends")
```

---

## Error Handling & Edge Cases

### Case 1: No Results Found

```
[Results Page]
├─ Icon: 🔍 or empty state
├─ Title: "No results found for 'your query'"
├─ Suggestions:
│  ├─ "Try a different phrasing"
│  ├─ "Search shorter keywords"
│  ├─ "Check RBAC: You might not have access to relevant docs"
├─ Actions:
│  ├─ [Rephrase query]
│  ├─ [Browse by topic]
│  ├─ [Contact admin to add docs]
│  └─ [Request documentation]
```

### Case 2: Query Failed / Timeout

```
[Results Page]
├─ Error banner: "⚠️ Query timed out after 30 seconds"
├─ What happened: "Likely temporary. We're searching across 50K+ documents."
├─ Actions:
│  ├─ [Retry]
│  ├─ [Try simpler query]
│  ├─ [Report issue]
│  └─ [Status page]
```

### Case 3: Data Source Out of Sync

```
[Alert in Admin Dashboard]
├─ ⚠️ "Notion sync is 6 hours stale (normally every hour)"
├─ Reason: "OAuth token may have expired"
├─ Actions:
│  ├─ [Manual sync now]
│  ├─ [Re-authenticate]
│  ├─ [View detailed logs]
│  └─ [Disable integration temporarily]
```

### Case 4: Hallucinated Answer (Critic Agent Caught It)

```
[Results Page]
├─ Warning banner: ⚠️ "This answer may not be accurate"
├─ Reason: "Our validation layer detected contradictions with source documents"
├─ Available sources: [Showing only the most confident sources]
├─ Actions:
│  ├─ [Flag as hallucination]
│  ├─ [Try rephrasing query]
│  ├─ [Manual search in data sources]
└─ [Contact support]
```

### Case 5: Insufficient Permissions

```
[Query Results]
├─ Censored banner: 🔒 "Some results are restricted to your role/team"
├─ Visible to you: [8 results]
├─ Hidden due to RBAC: [3 results]
├─ Actions:
│  ├─ [Request access]
│  ├─ [View allowed results only] (default)
│  └─ [Contact admin]
```

---

## Navigation & Information Architecture

### Top Navigation Bar (All Pages)

```
[Logo "Godspeed"] [Search Box (Cmd+K)] [Workspace ▼] [Profile ▼] [Notifications 🔔] [Help ❓]
```

### Left Sidebar (Collapsible)

**Engineers:**
```
- Dashboard (home)
- Query History
- Saved Searches (workspace)
- Trending Topics
- Help
- Settings > Appearance, Notifications, Data Export
```

**Managers:**
```
- Dashboard (home)
- Query Analytics
- Knowledge Health
- Dependency Tracker
- Team Settings
- Help
- Settings
```

**Admins:**
```
- Dashboard (home)
- Data Sources
- User Management
- RBAC Policies
- API Keys
- System Health
- Logs & Monitoring
- Settings
```

---

## Accessibility & Dark Mode

- All pages support **dark mode** toggle (Settings > Appearance)
- Keyboard navigation: Tab through elements, Enter/Space to activate
- WCAG 2.1 AA compliant (at minimum)
- Color contrast ratio ≥4.5:1 for text
- Focus indicators visible (outline or highlight)
- Screen reader support for data tables and graphs (aria-labels)

---

## Mobile Responsiveness

- **Engineers:** Primary use on desktop (query interface works on tablet, graphs on desktop only)
- **Managers:** Desktop-first (dashboards with multiple columns)
- **Admins:** Desktop-first (complex forms, large tables)
- Breakpoints: Mobile (320px), Tablet (768px), Desktop (1024px+)
- **Not planned for Phase 1:** Native mobile app (can be Phase 2 if demand exists)
