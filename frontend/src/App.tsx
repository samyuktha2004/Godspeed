import { Outlet, useLocation, useNavigate } from '@tanstack/react-router'
import { Suspense, useEffect, useRef } from 'react'
import { useUIStore } from '@/stores/uiStore'
import { useAuthStore } from '@/stores/authStore'
import { ToastStack } from '@/components/common/Toast'
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton'
import { NavBar } from '@/components/common/NavBar'
import { Sidebar } from '@/components/common/Sidebar'
import { cn } from '@/lib/utils'
import { env } from '@/config/env'

export default function App() {
  const theme       = useUIStore((s) => s.theme)
  const sidebarOpen = useUIStore((s) => s.sidebarOpen)
  const { pathname } = useLocation()
  const navigate    = useNavigate()
  const { user, login, logout } = useAuthStore()
  const validated   = useRef(false)

  // Sync theme class on <html>
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  // Validate persisted session against the server on first mount
  useEffect(() => {
    if (validated.current) return
    validated.current = true
    if (!user) return
    fetch(`${env.apiBaseUrl}/api/auth/refresh`, { method: 'POST', credentials: 'include' })
      .then(async (res) => {
        if (res.ok) {
          const { user: freshUser } = await res.json()
          login(freshUser)
        } else {
          logout()
          navigate({ to: '/login' })
        }
      })
      .catch(() => {
        // Network down — keep local state; lazy 401 handling via apiFetch
      })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ⌘K / Ctrl+K — jump to query
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        navigate({ to: '/query', search: { q: undefined } })
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [navigate])

  const isLoginPage = pathname === '/login'

  return (
    <div className="min-h-screen bg-surface font-sans text-stone-900 dark:bg-stone-950 dark:text-stone-100">

      {/* Mobile top nav — hidden on desktop */}
      {!isLoginPage && (
        <div className="lg:hidden">
          <NavBar />
        </div>
      )}

      {/* Desktop sidebar — hidden on mobile */}
      {!isLoginPage && (
        <div className="hidden lg:block">
          <Sidebar />
        </div>
      )}

      {/* Main content — offset by sidebar on desktop */}
      <main
        className={cn(
          'transition-[margin] duration-200 ease-in-out',
          !isLoginPage && (sidebarOpen ? 'lg:ml-60' : 'lg:ml-14'),
        )}
      >
        <Suspense fallback={<div className="p-8"><LoadingSkeleton rows={5} /></div>}>
          <Outlet />
        </Suspense>
      </main>

      <ToastStack />
    </div>
  )
}
