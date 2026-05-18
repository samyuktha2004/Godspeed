import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate } from '@tanstack/react-router'
import { useAuth } from '@/hooks/useAuth'
import { useUIStore } from '@/stores/uiStore'
import { env } from '@/config/env'

const schema = z.object({
  email:    z.string().email(),
  password: z.string().min(1),
})
type Fields = z.infer<typeof schema>

export default function LoginPage() {
  const { signIn }   = useAuth()
  const navigate     = useNavigate()
  const addToast     = useUIStore((s) => s.addToast)

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<Fields>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async (data: Fields) => {
    try {
      await signIn(data.email, data.password)
      navigate({ to: '/' })
    } catch (err) {
      addToast({ type: 'error', message: err instanceof Error ? err.message : 'Login failed' })
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <form
        onSubmit={handleSubmit(onSubmit)}
        className="flex w-full max-w-sm flex-col gap-4 rounded-xl border border-surface-subtle p-8 shadow-sm"
      >
        <h1 className="text-2xl font-semibold">Godspeed</h1>

        <label className="flex flex-col gap-1 text-sm">
          Email
          <input
            {...register('email')}
            type="email"
            autoComplete="email"
            className="rounded border border-surface-subtle bg-white px-3 py-2 text-stone-900 placeholder-stone-400 focus:outline-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
          />
          {errors.email && <span className="text-red-600 text-xs">{errors.email.message}</span>}
        </label>

        <label className="flex flex-col gap-1 text-sm">
          Password
          <input
            {...register('password')}
            type="password"
            autoComplete="current-password"
            className="rounded border border-surface-subtle bg-white px-3 py-2 text-stone-900 placeholder-stone-400 focus:outline-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
          />
          {errors.password && <span className="text-red-600 text-xs">{errors.password.message}</span>}
        </label>

        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded bg-brand py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-60"
        >
          {isSubmitting ? 'Signing in…' : 'Sign in'}
        </button>

        {/* Divider */}
        <div className="flex items-center gap-2">
          <hr className="flex-1 border-surface-subtle" />
          <span className="text-xs text-stone-400">or</span>
          <hr className="flex-1 border-surface-subtle" />
        </div>

        {/* Google SSO */}
        <a
          href={`${env.apiBaseUrl}/api/auth/google/authorize`}
          className="flex items-center justify-center gap-2 rounded border border-surface-subtle py-2 text-sm font-medium text-stone-700 hover:bg-stone-50 dark:text-stone-200 dark:hover:bg-stone-800"
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4" aria-hidden="true">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" />
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
          </svg>
          Sign in with Google
        </a>
      </form>
    </div>
  )
}
