import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { Link, useNavigate } from '@tanstack/react-router'
import { useAuthStore } from '@/stores/authStore'
import { useUIStore } from '@/stores/uiStore'
import { env } from '@/config/env'
import type { User } from '@/types/user'
import { isAdmin } from '@/lib/utils'

const schema = z.object({
  company_name: z.string().min(2, 'Company name is required'),
  name:         z.string().min(2, 'Your name is required'),
  email:        z.string().email('Enter a valid email'),
  password:     z.string().min(8, 'Minimum 8 characters'),
  confirm:      z.string(),
}).refine((d) => d.password === d.confirm, {
  message: 'Passwords do not match',
  path:    ['confirm'],
})
type Fields = z.infer<typeof schema>

function Field({
  label, error, children,
}: { label: string; error?: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      {label}
      {children}
      {error && <span className="text-xs text-red-600">{error}</span>}
    </label>
  )
}

const INPUT_CLASS =
  'rounded border border-surface-subtle bg-white px-3 py-2 text-stone-900 placeholder-stone-400 focus:outline-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white'

export default function RegisterPage() {
  const { login }  = useAuthStore()
  const addToast   = useUIStore((s) => s.addToast)
  const navigate   = useNavigate()

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Fields>({ resolver: zodResolver(schema) })

  const onSubmit = async (data: Fields) => {
    const res = await fetch(`${env.apiBaseUrl}/api/auth/register`, {
      method:      'POST',
      credentials: 'include',
      headers:     { 'Content-Type': 'application/json' },
      body:        JSON.stringify({
        company_name: data.company_name,
        name:         data.name,
        email:        data.email,
        password:     data.password,
      }),
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      addToast({ type: 'error', message: err.detail ?? 'Registration failed' })
      return
    }

    const { user }: { user: User } = await res.json()
    login(user)
    addToast({ type: 'success', message: `Welcome, ${user.name}!` })
    // org_admin goes to setup wizard; other roles (shouldn't happen on register) go home
    navigate({ to: isAdmin(user) ? '/setup' : '/' })
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-12">
      <div className="w-full max-w-sm">
        <form
          onSubmit={handleSubmit(onSubmit)}
          className="flex flex-col gap-4 rounded-xl border border-surface-subtle p-8 shadow-sm"
        >
          <div className="mb-1">
            <h1 className="text-2xl font-semibold">Create your workspace</h1>
            <p className="mt-1 text-sm text-stone-500">
              Set up Godspeed for your team in minutes.
            </p>
          </div>

          <Field label="Company name" error={errors.company_name?.message}>
            <input
              {...register('company_name')}
              type="text"
              placeholder="Acme Corp"
              autoComplete="organization"
              className={INPUT_CLASS}
            />
          </Field>

          <Field label="Your name" error={errors.name?.message}>
            <input
              {...register('name')}
              type="text"
              placeholder="Sam Yu"
              autoComplete="name"
              className={INPUT_CLASS}
            />
          </Field>

          <Field label="Work email" error={errors.email?.message}>
            <input
              {...register('email')}
              type="email"
              placeholder="you@company.com"
              autoComplete="email"
              className={INPUT_CLASS}
            />
          </Field>

          <Field label="Password" error={errors.password?.message}>
            <input
              {...register('password')}
              type="password"
              autoComplete="new-password"
              className={INPUT_CLASS}
            />
          </Field>

          <Field label="Confirm password" error={errors.confirm?.message}>
            <input
              {...register('confirm')}
              type="password"
              autoComplete="new-password"
              className={INPUT_CLASS}
            />
          </Field>

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-1 rounded bg-brand py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-60"
          >
            {isSubmitting ? 'Creating workspace…' : 'Create workspace'}
          </button>

          {/* Divider */}
          <div className="flex items-center gap-2">
            <hr className="flex-1 border-surface-subtle" />
            <span className="text-xs text-stone-400">or</span>
            <hr className="flex-1 border-surface-subtle" />
          </div>

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
            Continue with Google
          </a>
        </form>

        <p className="mt-4 text-center text-sm text-stone-500">
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-brand hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
