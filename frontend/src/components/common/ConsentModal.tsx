import { useState } from 'react'
import { apiFetch } from '@/lib/http'
import { useAuthStore } from '@/stores/authStore'
import { useUIStore } from '@/stores/uiStore'
import type { User } from '@/types/user'

/**
 * Blocking first-login DPDPA consent popup. Rendered by App whenever an
 * authenticated user has no recorded consent (consent_at is null/undefined).
 * Acknowledgement is persisted server-side via POST /api/auth/me/consent and
 * mirrored into the auth store so it does not reappear.
 */
export function ConsentModal() {
  const { login } = useAuthStore()
  const addToast  = useUIStore((s) => s.addToast)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleAgree = async () => {
    setIsSubmitting(true)
    try {
      const res = await apiFetch('/api/auth/me/consent', { method: 'POST' })
      const { user }: { user: User } = await res.json()
      login(user)
    } catch {
      addToast({ type: 'error', message: 'Could not record consent. Please try again.' })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="consent-title"
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
    >
      <div className="w-full max-w-md rounded-xl border border-surface-subtle bg-white p-6 shadow-xl dark:bg-stone-900">
        <h2 id="consent-title" className="mb-2 text-lg font-semibold">
          Before you continue
        </h2>
        <p className="text-sm text-stone-600 leading-relaxed dark:text-stone-300">
          Godspeed processes your name, work email, and the queries you run to provide search,
          analytics, and security logging. Your data is processed under India's Digital Personal Data
          Protection Act (DPDPA) and is not sold to third parties. You can request access to or erasure
          of your data at any time from{' '}
          <span className="font-medium">Settings → Privacy &amp; Data</span>.
        </p>
        <p className="mt-3 text-xs text-stone-500 leading-relaxed">
          Review our{' '}
          <a href="/privacy" target="_blank" rel="noopener noreferrer" className="text-brand hover:underline">Privacy Policy</a>
          {' '}and{' '}
          <a href="/terms" target="_blank" rel="noopener noreferrer" className="text-brand hover:underline">Terms of Service</a>.
        </p>

        <button
          onClick={handleAgree}
          disabled={isSubmitting}
          className="mt-6 w-full rounded bg-brand py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-60"
        >
          {isSubmitting ? 'Saving…' : 'I understand and agree'}
        </button>
      </div>
    </div>
  )
}
