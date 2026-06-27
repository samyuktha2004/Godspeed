import { Link, useLocation, useNavigate } from '@tanstack/react-router'
import { useUIStore } from '@/stores/uiStore'
import { useAuth } from '@/hooks/useAuth'
import { NotificationBell } from './NotificationBell'
import { cn, isAdmin, isManager } from '@/lib/utils'

const BASE_NAV = [
  { to: '/',          label: 'Home'      },
  { to: '/query',     label: 'Ask'       },
  { to: '/workspace', label: 'History'   },
  { to: '/analytics', label: 'Analytics' },
  { to: '/settings',  label: 'Settings'  },
]

const ADMIN_NAV   = { to: '/admin', label: 'Admin' }
const TEAM_NAV    = { to: '/team',  label: 'Team'  }

export function NavBar() {
  const theme       = useUIStore((s) => s.theme)
  const toggleTheme = useUIStore((s) => s.toggleTheme)
  const { pathname } = useLocation()
  const navigate    = useNavigate()
  const { user, signOut } = useAuth()
  const navLinks = isAdmin(user)
    ? [...BASE_NAV, TEAM_NAV, ADMIN_NAV]
    : isManager(user)
    ? [...BASE_NAV, TEAM_NAV]
    : BASE_NAV

  const handleSignOut = async () => {
    await signOut()
    navigate({ to: '/login' })
  }

  return (
    <header className="sticky top-0 z-30 border-b border-surface-subtle bg-white/80 backdrop-blur-sm dark:bg-stone-950/80">
      <div className="mx-auto flex h-12 max-w-7xl items-center gap-4 px-4">
        <Link to="/" className="shrink-0 text-sm font-semibold tracking-tight text-stone-900 dark:text-stone-100">
          Godspeed
        </Link>

        <nav className="flex flex-1 items-center gap-1 overflow-x-auto">
          {navLinks.map(({ to, label }) => {
            const active = to === '/' ? pathname === '/' : pathname.startsWith(to)
            return (
              <Link
                key={to}
                to={to}
                className={cn(
                  'whitespace-nowrap rounded-md px-3 py-1.5 text-sm transition-colors',
                  active
                    ? 'bg-stone-100 font-medium text-stone-900 dark:bg-stone-800 dark:text-stone-100'
                    : 'text-stone-500 hover:text-stone-700 dark:hover:text-stone-300',
                )}
              >
                {label}
              </Link>
            )
          })}
        </nav>

        <div className="flex shrink-0 items-center gap-2">
          <NotificationBell />

          {/* Theme toggle */}
          <button
            onClick={toggleTheme}
            className="rounded-md p-1.5 text-stone-500 hover:bg-stone-100 hover:text-stone-700 dark:hover:bg-stone-800 dark:hover:text-stone-300"
            aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
          >
            {theme === 'light' ? (
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z" />
              </svg>
            ) : (
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z" clipRule="evenodd" />
              </svg>
            )}
          </button>

          <kbd className="hidden rounded border border-stone-200 bg-stone-50 px-1.5 py-0.5 text-[10px] font-medium text-stone-400 dark:border-stone-700 dark:bg-stone-800 sm:inline">
            ⌘K
          </kbd>

          {/* User menu */}
          {user && (
            <div className="flex items-center gap-2 border-l border-surface-subtle pl-3">
              <span
                className="hidden text-xs text-stone-500 sm:inline truncate max-w-[120px]"
                title={user.email}
              >
                {user.name}
              </span>
              <span className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand text-[11px] font-semibold text-white">
                {user.name.charAt(0).toUpperCase()}
              </span>
              <button
                onClick={handleSignOut}
                className="rounded-md px-2 py-1 text-xs text-stone-500 hover:bg-stone-100 hover:text-stone-700 dark:hover:bg-stone-800 dark:hover:text-stone-300"
                title="Sign out"
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
