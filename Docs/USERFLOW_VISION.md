# User Flows — Original UX Vision (Not Yet Built)

> **Status: Aspirational.** These flows were part of the original UX design but are **not implemented** in the shipped frontend (cross-checked against [`PRD.md`](./PRD.md) known-gaps and [`TODO.md`](./TODO.md)). Kept here as a design reference for future work — not as documentation of current behavior.
>
> Before building any of these, re-check whether it's still wanted, whether a simpler version already shipped under a different name, or whether new product direction has made it unnecessary. See [`USERFLOW.md`](./USERFLOW.md) for what's actually live today.

---

## New Hire / Intern / Apprentice Flow

> Applies when `is_new_hire: true` OR the account has zero query history — a differentiated onboarding UX layered on top of the Engineer role. None of this exists today; all new-hire and existing-engineer accounts see the identical UI.

**Permissions:** Same as Engineer (RBAC-filtered to assigned team).

### Day-One Onboarding (First Login)

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
├─ Team context card:
│  ├─ "You've joined: [Backend Team]"
│  ├─ "Your team works with: [Service list from team's Neo4j nodes]"
│  └─ "Common topics your teammates ask about: [top 5 query topics for this team]"
├─ [Start guided tour — 3 steps] (dismissible)
└─ [Skip to search]
    │
    ▼ [3-step guided tour: what this is / how answers work / the knowledge graph]
    │
[Onboarding Dashboard — Home Page in New-Hire Mode]
├─ Starter Pack panel (replaces trending queries):
│  ├─ [ ] How do I set up my local dev environment?
│  ├─ [ ] What services does [team name] own?
│  ├─ [ ] Where are the runbooks for on-call?
│  ├─ [ ] How does deployment work here?
│  └─ [ ] Who do I contact for access to [X]?
│     (Clicking any of these fires it as a real query)
├─ Your mentor: [Name, assigned by manager] — "[Message]" button
├─ Useful links (admin-configured per team)
└─ Progress tracker: "You've asked [0] questions this week"
```

### First Query (New Hire Context)

```
[Home or Search]
    │
    ▼ [Short/vague query + is_new_hire]
    │
Frontend appends non-blocking hint: "💡 Try being more specific, e.g. 'How does X work in our codebase?'"
    │
    ▼
[Results — New Hire Extras]
├─ "New to this topic?" expandable card with suggested follow-ups + "Ask your mentor"
├─ If guardrail escalates: "This is a complex topic — consider asking [mentor name] directly."
└─ [Ask your mentor] → pre-filled message opens in Slack deep link / mailto
```

### Onboarding Progress (First Two Weeks)

```
[Home Page — New-Hire Mode, days 1–14]
├─ Progress tracker: "Week 1 goal: Ask 10 questions" → [████░░░░░░] 4/10
├─ Topics explored: badges
├─ "You've saved 2h of context-switching this week" (derived metric)
├─ Weekly digest email: top 5 queries + answers, team's current discussion topics
└─ [Dismiss new-hire mode] (day 3+, or auto-dismiss after 30 days / manager marks complete)
```

### Intern-Specific (Time-Bounded Account)

```
[Settings > Account]
├─ "Intern account — active until [date]"
├─ Exports available before expiry: query history, workspace PDF, email copy
├─ 7 days before expiry: "Your account expires in 7 days. Export your work."
└─ On expiry: account deactivated (data retained 90 days for compliance)
```

### Manager View of New Hires

```
[Analytics Dashboard] > [Team] > [New Hires tab]
├─ List: Name | Start date | Queries asked | Topics explored | Last active
├─ Knowledge gap indicator: topics asked 3+ times with low satisfaction = "needs support"
├─ Manager actions: [Mark onboarding complete] [Assign/change mentor] [Add starter pack question]
└─ Aggregate: "Average queries before first productive week: [X]"
```

---

## Workspace (Personal / Team / Shared Tabs)

```
[Sidebar] > [Workspace]
├─ Tabs: [Personal] [Team] [Shared with me]
├─ Personal: saved queries, saved result sets, notes
├─ Team: shared queries (manager-pinned), team runbooks, recurring analyses
├─ Shared with me: queries/results shared by colleagues
└─ Export: CSV / Markdown / PDF
```

Today only a flat query-history list exists (see [`USERFLOW.md`](./USERFLOW.md)) — no saving, tabs, sharing, or export.

## Share Results (Advanced)

```
[Results Page] > [Share]
├─ Copy shareable link, with expiry (never / 7d / 30d)
├─ Shared with: anyone with link / specific team / specific users
└─ Include-in-link toggles: answer, citations, graph, feedback history
```

Today "Share Results" (if present) sends only the query text, not graph state or full answer (PRD known gap).

## RBAC Policy Editor

```
[Admin Dashboard] > [RBAC Policies]
├─ List of policies (name, teams/users, data sources, doc-count preview)
├─ Create policy: who can access (teams/users) × which data sources × doc-type/age/tag filters
├─ Preview: "This policy will apply to [N] documents"
└─ Test access: "Test as user: alice@company.com" → shows what they'd see
```

## API Key Management

```
[Admin Dashboard] > [API Keys]
├─ List: name, created by, created, last used, permissions, [Rotate] [Revoke]
├─ Create: name, permission checkboxes, rate limits, expiry, IP whitelist
└─ Key shown once on creation with copy-to-clipboard + quick-start snippets
```

## User Management

```
[Admin Dashboard] > [User Management]
├─ List: user, email, role, team, status, [Edit] [Deactivate]
├─ Invite modal: email(s), role, team(s), permission checkboxes, optional message
└─ Bulk actions: add to team, assign role, deactivate multiple
```

Today, users/roles are configured via env vars for two personas (demo/admin) — there is no invite or user-list UI.

## Data Source Add Wizard (OAuth flow)

```
[Admin Dashboard] > [Data Sources] > [+ Add new source]
├─ Step 1: choose source type (Notion/Confluence/GitHub/Slack/Jira/PDF/URL/Other)
├─ Step 2: authenticate (OAuth flow or API key)
├─ Step 3: configure scope (workspaces/repos/spaces to sync)
├─ Step 4: test connection
├─ Step 5: confirm & set RBAC (who can access docs from this source)
└─ Step 6: monitor sync job (progress bar, live log, ETA)
```

Today, Data Sources is a static toggle list seeded from env vars — no add/configure wizard, no OAuth flow, no live sync progress.

## Dependency Tracker (Detailed Page)

```
[Analytics Dashboard] > [Dependencies]
├─ Alert banner: "N breaking changes in dependencies used by your team"
├─ Table: dependency, current/latest version, breaking changes, impact
├─ Per-row: [View changelog] [Request patch PR] [Dismiss for 30 days]
├─ Historical view: breaking changes this month, timeline
└─ Proactive notifications toggle per dependency
```

The shipped Dependencies tab shows version comparison and breaking-change flags from Neo4j nodes (see [`USERFLOW.md`](./USERFLOW.md)) but not changelog links, patch-PR requests, or per-dependency notification toggles — those depend on the Dependency Tracker pipeline, which [was never built].

## Team Settings (Manager)

```
[Analytics Dashboard] > [Team Settings]
├─ Team info: name, members, knowledge sources
├─ Data source permissions per team
├─ Analytics preferences: alert thresholds, weekly digest, report recipients
└─ Export/backup, archive/delete team
```

---

## Notification Types (full matrix, only partially wired)

| Event | Engineer | Manager | Admin |
|---|---|---|---|
| New docs match past query | ✓ | — | — |
| Escalation detected | — | ✓ | ✓ |
| Knowledge gap found | ✓ | ✓ | ✓ |
| Data source sync failed | — | — | ✓ |
| Query you asked now has better answer | ✓ | — | — |
| Team mentioned you in feedback | ✓ | ✓ | — |
| Breaking change in dependency | — | ✓ | ✓ |
| Credit warning | — | — | ✓ |
| User invited to team | ✓ (if team member) | — | ✓ |

`WS /ws` exists on the frontend but no backend event source produces any of these today (see [`USERFLOW.md`](./USERFLOW.md)).
