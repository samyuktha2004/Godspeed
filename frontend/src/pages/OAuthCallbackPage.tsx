import { useEffect } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useAuthStore } from '@/stores/authStore'
import { useUIStore } from '@/stores/uiStore'
import { env } from '@/config/env'
import type { User } from '@/types/user'

export default function OAuthCallbackPage() {
  const navigate  = useNavigate()
  const { login } = useAuthStore()
  const addToast  = useUIStore((s) => s.addToast)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const hasError = params.get('error') !== null

    if (hasError) {
      const error = params.get('error')
      const message = error === 'not_invited'
        ? 'Your Google account is not linked to any workspace. Ask an admin to invite you first.'
        : 'Google sign-in failed. Please try again.'
      addToast({ type: 'error', message })
      navigate({ to: '/login' })
      return
    }

    // The backend has already set the gs_session cookie.
    // Call refresh to hydrate the auth store — same path used on app mount.
    fetch(`${env.apiBaseUrl}/api/auth/refresh`, {
      method:      'POST',
      credentials: 'include',
    })
      .then(async (res) => {
        if (!res.ok) throw new Error('session not found')
        const { user }: { user: User } = await res.json()
        login(user)
        navigate({ to: '/' })
      })
      .catch(() => {
        addToast({ type: 'error', message: 'Could not complete sign-in. Please try again.' })
        navigate({ to: '/login' })
      })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="flex flex-col items-center gap-3 text-sm text-stone-500">
        <span className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-stone-200 border-t-stone-500" />
        Completing sign-in…
      </div>
    </div>
  )
}
