import { useState } from 'react'
import { X, Search, BookOpen, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { User } from '@/types/user'

const SEEN_KEY = 'gs_welcome_seen'

const STARTER_QUERIES: Record<User['role'], string[]> = {
  engineer: [
    'How do I set up local dev for the auth service?',
    'What caused the last P1 incident?',
    'Which services depend on the payments API?',
  ],
  manager: [
    'What are the open blockers across this sprint?',
    'Summarise last sprint's retro action items.',
    'Which services does the payments team depend on?',
  ],
  admin: [
    'How do I add a new data source?',
    'How do I invite team members?',
    'What is the current knowledge graph coverage?',
  ],
}

const FEATURES = [
  {
    icon:  Search,
    title: 'Ask in plain English',
    body:  'Ask questions the way you'd type them in Slack. No query syntax needed.',
  },
  {
    icon:  BookOpen,
    title: 'Cited answers',
    body:  'Every answer links back to the exact source — Jira ticket, Confluence page, or doc.',
  },
  {
    icon:  Zap,
    title: '⌘K anywhere',
    body:  'Press ⌘K (or Ctrl+K) from any page to jump straight to search.',
  },
]

interface Props {
  user:    User
  onQuery: (q: string) => void
}

export function WelcomeBanner({ user, onQuery }: Props) {
  const [visible, setVisible] = useState(true)

  const dismiss = () => {
    localStorage.setItem(SEEN_KEY, '1')
    setVisible(false)
  }

  if (!visible) return null

  const starters = STARTER_QUERIES[user.role] ?? STARTER_QUERIES.engineer

  return (
    <div className={cn(
      'relative rounded-xl border border-brand/20 bg-gradient-to-br from-brand/5 via-transparent to-transparent p-6',
      'dark:border-brand/30 dark:from-brand/10',
    )}>
      {/* Dismiss */}
      <button
        onClick={dismiss}
        aria-label="Dismiss welcome"
        className="absolute right-4 top-4 rounded-md p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-600 dark:hover:bg-stone-800"
      >
        <X className="h-4 w-4" />
      </button>

      {/* Header */}
      <div className="mb-5 pr-8">
        <h2 className="text-base font-semibold text-stone-900 dark:text-stone-100">
          Welcome to Godspeed, {user.name.split(' ')[0]}
        </h2>
        <p className="mt-0.5 text-sm text-stone-500">
          Your team's knowledge base, instantly searchable.
        </p>
      </div>

      {/* Feature pills */}
      <div className="mb-5 grid gap-3 sm:grid-cols-3">
        {FEATURES.map(({ icon: Icon, title, body }) => (
          <div
            key={title}
            className="rounded-lg border border-surface-subtle bg-white p-3.5 dark:bg-stone-900"
          >
            <div className="mb-2 flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-brand/10">
                <Icon className="h-3.5 w-3.5 text-brand" />
              </div>
              <p className="text-xs font-semibold text-stone-700 dark:text-stone-300">{title}</p>
            </div>
            <p className="text-xs text-stone-500 leading-relaxed">{body}</p>
          </div>
        ))}
      </div>

      {/* Starter queries */}
      <div>
        <p className="mb-2 text-xs font-medium text-stone-400 uppercase tracking-wide">
          Try asking
        </p>
        <div className="flex flex-wrap gap-2">
          {starters.map((q) => (
            <button
              key={q}
              onClick={() => { dismiss(); onQuery(q) }}
              className="rounded-full border border-surface-subtle bg-white px-3 py-1.5 text-xs text-stone-600 transition-colors hover:border-brand/40 hover:bg-brand/5 hover:text-brand dark:bg-stone-900 dark:text-stone-300"
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

export function shouldShowWelcome(user: User): boolean {
  return user.is_new_hire && !localStorage.getItem(SEEN_KEY)
}
