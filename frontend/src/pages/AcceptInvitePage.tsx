import { useEffect, useState } from 'react'
import { useNavigate, useSearch } from '@tanstack/react-router'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { useAuthStore } from '@/stores/authStore'
import { useUIStore } from '@/stores/uiStore'
import { env } from '@/config/env'
import type { User } from '@/types/user'

const schema = z.object({
  password: z.string().min(8, 'Minimum 8 characters'),
  confirm:  z.string(),
}).refine((d) => d.password === d.confirm, {
  message: 'Passwords do not match',
  path:    ['confirm'],
})
type Fields = z.infer<typeof schema>

export default function AcceptInvitePage() {
  const { token } = useSearch({ from: '/accept-invite' })
  const navigate   = useNavigate()
  const { login }  = useAuthStore()
  const addToast   = useUIStore((s) => s.addToast)

  const [invite, setInvite] = useState<{ email: string; name: string; role: string } | null>(null)
  const [loading, setLoading] = useState(true)

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Fields>({
    resolver: zodResolver(schema),
  })

  // Load invite info from token
  useEffect(() => {
    if (!token) { navigate({ to: '/login' }); return }
    fetch(`${env.apiBaseUrl}/api/auth/invite/${token}`, { credentials: 'include' })
      .then(async (res) => {
        if (!res.ok) throw new Error('Invite link is invalid or has expired')
        setInvite(await res.json())
      })
      .catch((err) => {
        addToast({ type: 'error', message: err.message })
        navigate({ to: '/login' })
      })
      .finally(() => setLoading(false))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const onSubmit = async ({ password }: Fields) => {
    const res = await fetch(`${env.apiBaseUrl}/api/auth/accept-invite`, {
      method:      'POST',
      credentials: 'include',
      headers:     { 'Content-Type': 'application/json' },
      body:        JSON.stringify({ token, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      addToast({ type: 'error', message: err.detail ?? 'Failed to accept invite' })
      return
    }
    const { user }: { user: User } = await res.json()
    login(user)
    addToast({ type: 'success', message: `Welcome, ${user.name}!` })
    navigate({ to: '/' })
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <span className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-stone-200 border-t-stone-500" />
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <form
        onSubmit={handleSubmit(onSubmit)}
        className="flex w-full max-w-sm flex-col gap-4 rounded-xl border border-surface-subtle p-8 shadow-sm"
      >
        <div>
          <h1 className="text-2xl font-semibold">Accept invite</h1>
          {invite && (
            <p className="mt-1 text-sm text-stone-500">
              You've been invited as <span className="font-medium capitalize">{invite.role}</span>
              {' '}— {invite.email}
            </p>
          )}
        </div>

        <label className="flex flex-col gap-1 text-sm">
          Password
          <input
            {...register('password')}
            type="password"
            autoComplete="new-password"
            className="rounded border border-surface-subtle bg-white px-3 py-2 text-stone-900 placeholder-stone-400 focus:outline-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
          />
          {errors.password && <span className="text-xs text-red-600">{errors.password.message}</span>}
        </label>

        <label className="flex flex-col gap-1 text-sm">
          Confirm password
          <input
            {...register('confirm')}
            type="password"
            autoComplete="new-password"
            className="rounded border border-surface-subtle bg-white px-3 py-2 text-stone-900 placeholder-stone-400 focus:outline-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
          />
          {errors.confirm && <span className="text-xs text-red-600">{errors.confirm.message}</span>}
        </label>

        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded bg-brand py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-60"
        >
          {isSubmitting ? 'Setting up account…' : 'Set password & join'}
        </button>

        <p className="text-xs text-stone-400 leading-relaxed">
          By joining, you agree to Godspeed's{' '}
          <a href="/terms" target="_blank" rel="noopener noreferrer" className="text-brand hover:underline">Terms of Service</a>
          {' '}and{' '}
          <a href="/privacy" target="_blank" rel="noopener noreferrer" className="text-brand hover:underline">Privacy Policy</a>.
          Your personal data will be processed in accordance with applicable law, including India's DPDPA.
        </p>
      </form>
    </div>
  )
}
