import { useNavigate, useLocation, Link } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import {
  Home, Search, Clock, BarChart2, Settings2, LogOut,
  Sun, Moon, ChevronLeft, ChevronRight, Zap, Bell,
} from 'lucide-react'
import { useUIStore } from '@/stores/uiStore'
import { useAuth } from '@/hooks/useAuth'
import { useNotifications } from '@/hooks/useNotifications'
import { NotificationCenter } from './NotificationCenter'
import { apiFetch } from '@/lib/http'
import { cn } from '@/lib/utils'
import { useState } from 'react'

// ─── Types ────────────────────────────────────────────────────────────────────

interface RecentQuery {
  id:         string
  query:      string
  created_at: string
  success:    boolean
}

// ─── Data fetching ────────────────────────────────────────────────────────────

async function fetchRecentQueries(): Promise<RecentQuery[]> {
  const res  = await apiFetch('/api/workspace/history?page=1&limit=6')
  const data = await res.json()
  return (data.items ?? []) as RecentQuery[]
}

// ─── Nav definition ───────────────────────────────────────────────────────────

const BASE_NAV = [
  { to: '/',          Icon: Home,      label: 'Home'      },
  { to: '/query',     Icon: Search,    label: 'Ask'       },
  { to: '/workspace', Icon: Clock,     label: 'History'   },
  { to: '/analytics', Icon: BarChart2, label: 'Analytics' },
]
const ADMIN_NAV = { to: '/admin', Icon: Settings2, label: 'Admin' }

// ─── Sidebar ──────────────────────────────────────────────────────────────────

export function Sidebar() {
  const { sidebarOpen, toggleSidebar, theme, toggleTheme } = useUIStore()
  const { user, signOut } = useAuth()
  const navigate          = useNavigate()
  const { pathname }      = useLocation()
  const { unreadCount }   = useNotifications()
  const [notifOpen, setNotifOpen] = useState(false)

  const { data: recent = [] } = useQuery({
    queryKey:        ['sidebar-recent'],
    queryFn:         fetchRecentQueries,
    staleTime:       30_000,
    refetchInterval: 60_000,
    enabled:         !!user,
  })

  const handleSignOut = async () => {
    await signOut()
    navigate({ to: '/login' })
  }

  const navItems = user?.role === 'admin'
    ? [...BASE_NAV, ADMIN_NAV]
    : BASE_NAV

  return (
    <>
      <aside
        className={cn(
          'fixed left-0 top-0 z-20 flex h-screen flex-col border-r border-surface-subtle bg-white transition-[width] duration-200 ease-in-out dark:bg-stone-950',
          sidebarOpen ? 'w-60' : 'w-14',
        )}
      >
        {/* ── Header: logo + collapse toggle ─────────────────────────────── */}
        <div className="flex h-12 shrink-0 items-center gap-2 border-b border-surface-subtle px-3">
          {sidebarOpen && (
            <Link
              to="/"
              className="flex min-w-0 flex-1 items-center gap-2 text-sm font-semibold tracking-tight text-stone-900 dark:text-stone-100"
            >
              <Zap className="h-4 w-4 shrink-0 text-brand" />
              Godspeed
            </Link>
          )}
          {!sidebarOpen && <Zap className="mx-auto h-4 w-4 text-brand" />}

          <button
            onClick={toggleSidebar}
            className={cn(
              'shrink-0 rounded-md p-1.5 text-stone-400 hover:bg-stone-100 hover:text-stone-600 dark:hover:bg-stone-800 dark:hover:text-stone-300',
              !sidebarOpen && 'mx-auto',
            )}
            aria-label={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          >
            {sidebarOpen
              ? <ChevronLeft className="h-4 w-4" />
              : <ChevronRight className="h-4 w-4" />}
          </button>
        </div>

        {/* ── Navigation links ────────────────────────────────────────────── */}
        <nav className="flex flex-col gap-0.5 p-2 pt-3">
          {navItems.map(({ to, Icon, label }) => {
            const active = to === '/' ? pathname === '/' : pathname.startsWith(to)
            return (
              <Link
                key={to}
                to={to}
                title={!sidebarOpen ? label : undefined}
                className={cn(
                  'flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm transition-colors',
                  active
                    ? 'bg-stone-100 font-medium text-stone-900 dark:bg-stone-800 dark:text-stone-100'
                    : 'text-stone-500 hover:bg-stone-50 hover:text-stone-800 dark:hover:bg-stone-900 dark:hover:text-stone-200',
                  !sidebarOpen && 'justify-center px-2',
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {sidebarOpen && (
                  <>
                    <span className="flex-1">{label}</span>
                    {label === 'Ask' && (
                      <kbd className="rounded border border-stone-200 bg-stone-50 px-1 py-0.5 text-[9px] font-medium text-stone-400 dark:border-stone-700 dark:bg-stone-800">
                        ⌘K
                      </kbd>
                    )}
                  </>
                )}
              </Link>
            )
          })}

          {/* Notifications */}
          <button
            onClick={() => setNotifOpen(true)}
            title={!sidebarOpen ? 'Notifications' : undefined}
            className={cn(
              'relative flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm text-stone-500 transition-colors hover:bg-stone-50 hover:text-stone-800 dark:hover:bg-stone-900 dark:hover:text-stone-200',
              !sidebarOpen && 'justify-center px-2',
            )}
          >
            <Bell className="h-4 w-4 shrink-0" />
            {sidebarOpen && <span className="flex-1 text-left">Notifications</span>}
            {unreadCount > 0 && (
              <span className={cn(
                'flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-brand px-1 text-[10px] font-bold text-white',
                !sidebarOpen && 'absolute right-1.5 top-1.5',
              )}>
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>
        </nav>

        {/* ── Recent queries ─────────────────────────────────────────────── */}
        {sidebarOpen && recent.length > 0 && (
          <div className="mt-1 px-2">
            <p className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-stone-400">
              Recent
            </p>
            <div className="flex flex-col gap-0.5">
              {recent.map((item) => (
                <button
                  key={item.id}
                  onClick={() => navigate({ to: '/query', search: { q: item.query } })}
                  title={item.query}
                  className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left transition-colors hover:bg-stone-50 dark:hover:bg-stone-900"
                >
                  <span
                    className={cn(
                      'h-1.5 w-1.5 shrink-0 rounded-full',
                      item.success ? 'bg-green-400' : 'bg-stone-300',
                    )}
                  />
                  <span className="truncate text-xs text-stone-500 dark:text-stone-400">
                    {item.query.length > 34 ? item.query.slice(0, 34) + '…' : item.query}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* ── Spacer ─────────────────────────────────────────────────────── */}
        <div className="flex-1" />

        {/* ── Bottom: theme + account ─────────────────────────────────────── */}
        <div className="border-t border-surface-subtle p-2">
          {/* Theme toggle */}
          <button
            onClick={toggleTheme}
            title={!sidebarOpen ? (theme === 'light' ? 'Dark mode' : 'Light mode') : undefined}
            className={cn(
              'flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-sm text-stone-500 transition-colors hover:bg-stone-50 hover:text-stone-800 dark:hover:bg-stone-900 dark:hover:text-stone-200',
              !sidebarOpen && 'justify-center px-2',
            )}
          >
            {theme === 'light'
              ? <Moon className="h-4 w-4 shrink-0" />
              : <Sun  className="h-4 w-4 shrink-0" />}
            {sidebarOpen && <span>{theme === 'light' ? 'Dark mode' : 'Light mode'}</span>}
          </button>

          {/* User section */}
          {user && (
            <div className={cn(
              'mt-1 flex items-center gap-2 rounded-lg px-2 py-2',
              !sidebarOpen && 'justify-center',
            )}>
              {/* Avatar */}
              <span
                title={!sidebarOpen ? user.name : undefined}
                className="inline-flex h-7 w-7 shrink-0 cursor-default items-center justify-center rounded-full bg-brand text-[11px] font-semibold text-white"
              >
                {user.name.charAt(0).toUpperCase()}
              </span>

              {sidebarOpen && (
                <>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium text-stone-700 dark:text-stone-300">
                      {user.name}
                    </p>
                    <p className="truncate text-[10px] text-stone-400">{user.email}</p>
                  </div>
                  <button
                    onClick={handleSignOut}
                    title="Sign out"
                    className="shrink-0 rounded-md p-1.5 text-stone-400 hover:bg-stone-100 hover:text-stone-700 dark:hover:bg-stone-800 dark:hover:text-stone-300"
                    aria-label="Sign out"
                  >
                    <LogOut className="h-3.5 w-3.5" />
                  </button>
                </>
              )}
            </div>
          )}
        </div>
      </aside>

      {/* Notification center — portal-rendered */}
      <NotificationCenter open={notifOpen} onClose={() => setNotifOpen(false)} />
    </>
  )
}
