import { useCallback } from 'react'
import { useAuthStore } from '@/stores/authStore'
import { apiFetch } from '@/lib/http'
import type { User } from '@/types/user'

export function useAuth() {
  const { user, isAuthenticated, login, logout } = useAuthStore()

  const signIn = useCallback(
    async (email: string, password: string): Promise<void> => {
      const res = await apiFetch('/api/auth/login', {
        method: 'POST',
        body:   JSON.stringify({ email, password }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Login failed' }))
        throw new Error(err.detail ?? 'Login failed')
      }
      const { user: userData }: { user: User } = await res.json()
      login(userData)
    },
    [login],
  )

  const signOut = useCallback(async () => {
    await apiFetch('/api/auth/logout', { method: 'POST' }).catch(() => {})
    logout()
  }, [logout])

  return { user, isAuthenticated, signIn, signOut }
}
