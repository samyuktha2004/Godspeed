import { useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { useQuery, useMutation } from '@tanstack/react-query'
import { apiFetch } from '@/lib/http'
import { useUIStore } from '@/stores/uiStore'
import type { WorkspaceSettings } from '@/types/settings'

const schema = z.object({
  name:              z.string().min(2, 'Name is required'),
  slug:              z.string().min(2, 'Slug is required').regex(/^[a-z0-9-]+$/, 'Lowercase letters, numbers, hyphens only'),
  description:       z.string().optional(),
  max_team_members:  z.coerce.number().int().positive().optional().or(z.literal('')),
  max_channels:      z.coerce.number().int().positive().optional().or(z.literal('')),
})
type Fields = z.infer<typeof schema>

async function fetchWorkspace(): Promise<WorkspaceSettings> {
  const res = await apiFetch('/api/admin/workspace')
  return res.json()
}

async function updateWorkspace(data: Partial<WorkspaceSettings>): Promise<WorkspaceSettings> {
  const res = await apiFetch('/api/admin/workspace', {
    method:  'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(data),
  })
  return res.json()
}

const LABEL  = 'block text-xs font-medium text-stone-600 dark:text-stone-400 mb-1'
const INPUT  = 'block w-full rounded border border-surface-subtle bg-white px-3 py-2 text-sm text-stone-900 placeholder-stone-400 focus:outline-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white'

export function AdminWorkspaceSettings() {
  const addToast = useUIStore((s) => s.addToast)

  const { data: workspace } = useQuery({
    queryKey: ['admin-workspace'],
    queryFn:  fetchWorkspace,
    staleTime: 60_000,
  })

  const { register, handleSubmit, reset, formState: { errors, isDirty } } = useForm<Fields>({
    resolver: zodResolver(schema),
  })

  useEffect(() => {
    if (workspace) reset(workspace)
  }, [workspace, reset])

  const save = useMutation({
    mutationFn: updateWorkspace,
    onSuccess:  () => addToast({ type: 'success', message: 'Workspace settings saved' }),
    onError:    () => addToast({ type: 'error',   message: 'Failed to save settings' }),
  })

  const onSubmit = (data: Fields) => save.mutate(data as Partial<WorkspaceSettings>)

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-8 p-6">
      {/* Basic info */}
      <div className="flex flex-col gap-4">
        <p className="text-sm font-medium">Workspace info</p>
        <div>
          <label className={LABEL}>Name</label>
          <input {...register('name')} type="text" className={INPUT} />
          {errors.name && <p className="mt-1 text-xs text-red-600">{errors.name.message}</p>}
        </div>
        <div>
          <label className={LABEL}>URL slug</label>
          <input {...register('slug')} type="text" className={INPUT} />
          {errors.slug && <p className="mt-1 text-xs text-red-600">{errors.slug.message}</p>}
          <p className="mt-1 text-xs text-stone-400">Lowercase letters, numbers, and hyphens only.</p>
        </div>
        <div>
          <label className={LABEL}>Description</label>
          <textarea {...register('description')} rows={3} className={INPUT} />
        </div>
      </div>

      {/* Limits */}
      <div className="flex flex-col gap-4 border-t border-surface-subtle pt-6">
        <p className="text-sm font-medium">Limits</p>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className={LABEL}>Max team members</label>
            <input {...register('max_team_members')} type="number" min={1} className={INPUT} placeholder="Unlimited" />
          </div>
          <div>
            <label className={LABEL}>Max channels</label>
            <input {...register('max_channels')} type="number" min={1} className={INPUT} placeholder="Unlimited" />
          </div>
        </div>
      </div>

      <div>
        <button
          type="submit"
          disabled={!isDirty || save.isPending}
          className="rounded-lg bg-brand px-5 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-60"
        >
          {save.isPending ? 'Saving…' : 'Save changes'}
        </button>
      </div>

      {/* Danger zone */}
      <div className="flex flex-col gap-3 rounded-xl border border-red-200 p-4 dark:border-red-900">
        <p className="text-sm font-semibold text-red-700 dark:text-red-400">Danger zone</p>
        <div>
          <p className="text-sm font-medium text-stone-700 dark:text-stone-300">Delete this workspace</p>
          <p className="mt-0.5 text-xs text-stone-500">
            Permanently deletes all data, users, and documents. This cannot be undone.
          </p>
          <button
            type="button"
            className="mt-3 rounded-lg bg-red-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-red-700"
            onClick={() => window.confirm('Delete this workspace? This cannot be undone.') && addToast({ type: 'error', message: 'Workspace deletion is disabled in this environment.' })}
          >
            Delete workspace
          </button>
        </div>
      </div>
    </form>
  )
}
