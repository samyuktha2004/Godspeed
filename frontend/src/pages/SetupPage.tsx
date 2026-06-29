import { useState } from 'react'
import { useNavigate } from '@tanstack/react-router'
import { useForm, useFieldArray } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { Database, Users, CheckCircle, Plus, X } from 'lucide-react'
import { useAuthStore } from '@/stores/authStore'
import { useUIStore } from '@/stores/uiStore'
import { apiFetch } from '@/lib/http'
import { cn } from '@/lib/utils'

// ── Step indicator ────────────────────────────────────────────────────────────

const STEPS = [
  { id: 1, label: 'Connect Sources', icon: Database },
  { id: 2, label: 'Invite Team',     icon: Users    },
  { id: 3, label: 'Ready',           icon: CheckCircle },
]

function StepIndicator({ current }: { current: number }) {
  return (
    <div className="flex items-center justify-center gap-0">
      {STEPS.map((step, i) => {
        const done   = step.id < current
        const active = step.id === current
        const Icon   = step.icon
        return (
          <div key={step.id} className="flex items-center">
            <div className="flex flex-col items-center gap-1.5">
              <div className={cn(
                'flex h-9 w-9 items-center justify-center rounded-full border-2 transition-colors',
                done   && 'border-brand bg-brand text-white',
                active && 'border-brand bg-white text-brand dark:bg-stone-900',
                !done && !active && 'border-stone-200 bg-white text-stone-300 dark:border-stone-700 dark:bg-stone-900',
              )}>
                {done
                  ? <CheckCircle className="h-4 w-4" />
                  : <Icon className="h-4 w-4" />}
              </div>
              <span className={cn(
                'text-[11px] font-medium',
                active ? 'text-brand' : done ? 'text-stone-500' : 'text-stone-300 dark:text-stone-600',
              )}>
                {step.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={cn(
                'mx-3 mb-5 h-px w-16 transition-colors',
                done ? 'bg-brand' : 'bg-stone-200 dark:bg-stone-700',
              )} />
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Step 1: Connect Sources ───────────────────────────────────────────────────

const sourceSchema = z.object({
  jira_url:        z.string().url('Enter a valid URL').optional().or(z.literal('')),
  jira_token:      z.string().optional(),
  confluence_url:  z.string().url('Enter a valid URL').optional().or(z.literal('')),
  confluence_token: z.string().optional(),
})
type SourceFields = z.infer<typeof sourceSchema>

const INPUT = 'w-full rounded border border-surface-subtle bg-white px-3 py-2 text-sm text-stone-900 placeholder-stone-400 focus:outline-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white'
const LABEL = 'block mb-1 text-xs font-medium text-stone-500'

function Step1Sources({ onNext, onSkip }: { onNext: () => void; onSkip: () => void }) {
  const addToast = useUIStore((s) => s.addToast)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SourceFields>({ resolver: zodResolver(sourceSchema) })

  const onSubmit = async (data: SourceFields) => {
    const sources = []
    if (data.jira_url)       sources.push({ type: 'jira',       url: data.jira_url,       api_token: data.jira_token       })
    if (data.confluence_url) sources.push({ type: 'confluence', url: data.confluence_url, api_token: data.confluence_token })

    if (sources.length === 0) { onNext(); return }

    try {
      await Promise.all(
        sources.map((s) =>
          apiFetch('/api/admin/data-sources', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...s, name: s.type === 'jira' ? 'Jira' : 'Confluence', enabled: true }),
          }),
        ),
      )
      addToast({ type: 'success', message: `${sources.length} source${sources.length > 1 ? 's' : ''} connected` })
      onNext()
    } catch {
      addToast({ type: 'error', message: 'Failed to connect sources — you can configure them later in Admin.' })
      onNext()
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-semibold">Connect your knowledge sources</h2>
        <p className="mt-1 text-sm text-stone-500">
          Godspeed will index these and make them searchable. You can add more sources later.
        </p>
      </div>

      {/* Jira */}
      <div className="rounded-xl border border-surface-subtle p-4">
        <div className="mb-3 flex items-center gap-2">
          <span className="text-lg" aria-hidden>🔷</span>
          <p className="font-medium text-sm">Jira</p>
          <span className="ml-auto text-xs text-stone-400">Optional</span>
        </div>
        <div className="flex flex-col gap-3">
          <div>
            <label className={LABEL}>Site URL</label>
            <input
              {...register('jira_url')}
              type="url"
              placeholder="https://yourcompany.atlassian.net"
              className={INPUT}
            />
            {errors.jira_url && <p className="mt-1 text-xs text-red-600">{errors.jira_url.message}</p>}
          </div>
          <div>
            <label className={LABEL}>API Token</label>
            <input
              {...register('jira_token')}
              type="password"
              placeholder="Your Atlassian API token"
              className={INPUT}
            />
          </div>
        </div>
      </div>

      {/* Confluence */}
      <div className="rounded-xl border border-surface-subtle p-4">
        <div className="mb-3 flex items-center gap-2">
          <span className="text-lg" aria-hidden>📘</span>
          <p className="font-medium text-sm">Confluence</p>
          <span className="ml-auto text-xs text-stone-400">Optional</span>
        </div>
        <div className="flex flex-col gap-3">
          <div>
            <label className={LABEL}>Site URL</label>
            <input
              {...register('confluence_url')}
              type="url"
              placeholder="https://yourcompany.atlassian.net/wiki"
              className={INPUT}
            />
            {errors.confluence_url && <p className="mt-1 text-xs text-red-600">{errors.confluence_url.message}</p>}
          </div>
          <div>
            <label className={LABEL}>API Token</label>
            <input
              {...register('confluence_token')}
              type="password"
              placeholder="Your Atlassian API token"
              className={INPUT}
            />
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={onSkip}
          className="text-sm text-stone-400 hover:text-stone-600"
        >
          Skip for now
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-lg bg-brand px-5 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-60"
        >
          {isSubmitting ? 'Connecting…' : 'Connect & continue'}
        </button>
      </div>
    </form>
  )
}

// ── Step 2: Invite Team ───────────────────────────────────────────────────────

const inviteSchema = z.object({
  invites: z.array(z.object({
    email: z.string().email('Enter a valid email').or(z.literal('')),
    role:  z.enum(['engineer', 'manager']),
  })),
})
type InviteFields = z.infer<typeof inviteSchema>

function Step2Invite({ onNext, onSkip }: { onNext: () => void; onSkip: () => void }) {
  const addToast = useUIStore((s) => s.addToast)
  const { register, control, handleSubmit, formState: { isSubmitting } } = useForm<InviteFields>({
    resolver: zodResolver(inviteSchema),
    defaultValues: { invites: [{ email: '', role: 'engineer' }] },
  })
  const { fields, append, remove } = useFieldArray({ control, name: 'invites' })

  const onSubmit = async (data: InviteFields) => {
    const valid = data.invites.filter((i) => i.email.trim())
    if (valid.length === 0) { onNext(); return }

    let sent = 0
    await Promise.all(
      valid.map(async (invite) => {
        try {
          await apiFetch('/api/admin/users/invite', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(invite),
          })
          sent++
        } catch { /* individual failures are silent — we'll report the total */ }
      }),
    )

    if (sent > 0) {
      addToast({ type: 'success', message: `${sent} invite${sent > 1 ? 's' : ''} sent` })
    } else {
      addToast({ type: 'warning', message: 'Invites could not be sent — try again from Admin → Users.' })
    }
    onNext()
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-6">
      <div>
        <h2 className="text-lg font-semibold">Invite your team</h2>
        <p className="mt-1 text-sm text-stone-500">
          Team members will receive an email to set their password and join.
        </p>
      </div>

      <div className="flex flex-col gap-2">
        {fields.map((field, i) => (
          <div key={field.id} className="flex items-center gap-2">
            <input
              {...register(`invites.${i}.email`)}
              type="email"
              placeholder="colleague@company.com"
              className={cn(INPUT, 'flex-1')}
            />
            <select
              {...register(`invites.${i}.role`)}
              className="rounded border border-surface-subtle bg-white px-2 py-2 text-sm text-stone-700 focus:outline-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
            >
              <option value="engineer">Engineer</option>
              <option value="manager">Manager</option>
            </select>
            {fields.length > 1 && (
              <button
                type="button"
                onClick={() => remove(i)}
                className="rounded p-1 text-stone-400 hover:text-red-500"
                aria-label="Remove"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        ))}

        <button
          type="button"
          onClick={() => append({ email: '', role: 'engineer' })}
          className="flex w-fit items-center gap-1.5 text-sm text-brand hover:underline"
        >
          <Plus className="h-3.5 w-3.5" />
          Add another
        </button>
      </div>

      <div className="flex items-center justify-between">
        <button
          type="button"
          onClick={onSkip}
          className="text-sm text-stone-400 hover:text-stone-600"
        >
          Skip for now
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-lg bg-brand px-5 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-60"
        >
          {isSubmitting ? 'Sending…' : 'Send invites & continue'}
        </button>
      </div>
    </form>
  )
}

// ── Step 3: Ready ─────────────────────────────────────────────────────────────

function Step3Ready({ onDone }: { onDone: () => void }) {
  return (
    <div className="flex flex-col items-center gap-6 py-6 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-brand/10">
        <CheckCircle className="h-8 w-8 text-brand" />
      </div>
      <div>
        <h2 className="text-xl font-semibold">Your workspace is ready</h2>
        <p className="mt-2 text-sm text-stone-500">
          Godspeed is indexing your sources in the background. Results will appear as data is ingested.
        </p>
      </div>
      <ul className="w-full max-w-xs space-y-2 text-left">
        {[
          'Ask anything using the search bar',
          'View your knowledge graph in real time',
          'Manage sources and users in Admin',
        ].map((tip) => (
          <li key={tip} className="flex items-start gap-2 text-sm text-stone-600 dark:text-stone-400">
            <span className="mt-0.5 text-brand">✓</span>
            {tip}
          </li>
        ))}
      </ul>
      <button
        onClick={onDone}
        className="rounded-lg bg-brand px-6 py-2.5 text-sm font-medium text-white hover:bg-brand-dark"
      >
        Go to dashboard
      </button>
    </div>
  )
}

// ── Main wizard ───────────────────────────────────────────────────────────────

export default function SetupPage() {
  const [step, setStep]             = useState(1)
  const { markSetupComplete, user } = useAuthStore()
  const navigate                    = useNavigate()

  const next = () => setStep((s) => Math.min(s + 1, 3))
  const done = () => {
    markSetupComplete()
    navigate({ to: '/' })
  }

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-12">
      {/* Logo */}
      <div className="mb-8 flex items-center gap-2">
        <span className="text-brand">⚡</span>
        <span className="text-lg font-semibold tracking-tight">Godspeed</span>
      </div>

      <div className="w-full max-w-xl">
        {/* Step indicator */}
        <div className="mb-8">
          <StepIndicator current={step} />
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-surface-subtle bg-white p-8 shadow-sm dark:bg-stone-900">
          {user && (
            <p className="mb-6 text-xs text-stone-400">
              Setting up workspace for <span className="font-medium text-stone-600 dark:text-stone-300">{user.email}</span>
            </p>
          )}
          {step === 1 && <Step1Sources onNext={next} onSkip={next} />}
          {step === 2 && <Step2Invite  onNext={next} onSkip={next} />}
          {step === 3 && <Step3Ready   onDone={done} />}
        </div>

        <p className="mt-4 text-center text-xs text-stone-400">
          You can change any of this later in{' '}
          <button
            onClick={done}
            className="underline hover:text-stone-600"
          >
            Admin settings
          </button>
          .
        </p>
      </div>
    </div>
  )
}
