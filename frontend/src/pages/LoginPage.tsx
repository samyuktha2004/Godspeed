import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { useNavigate } from '@tanstack/react-router'
import { useAuth } from '@/hooks/useAuth'
import { useUIStore } from '@/stores/uiStore'

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
            className="rounded border border-surface-subtle px-3 py-2 focus:outline-brand"
          />
          {errors.email && <span className="text-red-600 text-xs">{errors.email.message}</span>}
        </label>

        <label className="flex flex-col gap-1 text-sm">
          Password
          <input
            {...register('password')}
            type="password"
            autoComplete="current-password"
            className="rounded border border-surface-subtle px-3 py-2 focus:outline-brand"
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
      </form>
    </div>
  )
}
