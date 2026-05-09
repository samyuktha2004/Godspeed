import { Outlet, useLocation, useNavigate } from '@tanstack/react-router'
import { Suspense, useEffect, useRef } from 'react'
import { useUIStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import { ToastStack } from '@/components/common/Toast'
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton'
import { NavBar } from '@/components/common/NavBar'
import { env } from '@/config/env'

export default function App() {
  const theme    = useUIStore((s) => s.theme)
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const { user, login, logout } = useAuthStore()
  const validated = useRef(false)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  // Validate persisted session against the server on first mount.
  // Prevents stale localStorage state from granting access after server-side expiry.
  useEffect(() => {
    if (validated.current) return
    validated.current = true

    if (!user) return // not logged in — no need to check

    fetch(`${env.apiBaseUrl}/api/auth/refresh`, {
      method:      'POST',
      credentials: 'include',
    })
      .then(async (res) => {
        if (res.ok) {
          const { user: freshUser } = await res.json()
          login(freshUser) // refresh user data in case role/team changed
        } else {
          // Server rejected the session — clear local state
          logout()
          navigate({ to: '/login' })
        }
      })
      .catch(() => {
        // Network down — keep local state, apiFetch will handle 401s lazily
      })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Cmd+K / Ctrl+K — jump to query page
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        navigate({ to: '/query' })
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [navigate])

  const isLoginPage = pathname === '/login'

  return (
    <div className="min-h-screen bg-surface font-sans text-stone-900 dark:bg-stone-950 dark:text-stone-100">
      {!isLoginPage && <NavBar />}
      <Suspense fallback={<LoadingSkeleton />}>
        <Outlet />
      </Suspense>
      <ToastStack />
    </div>
  )
}
