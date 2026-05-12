import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { WorkspaceSettings } from '@/types/settings'

export function AdminWorkspaceSettings() {
  const { register, handleSubmit, formState: { errors } } = useForm<WorkspaceSettings>({
    defaultValues: {
      name: 'Godspeed',
      slug: 'godspeed',
      description: 'Engineering knowledge base',
    },
  })
  const [isSaving, setIsSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const onSubmit = async (data: WorkspaceSettings) => {
    setIsSaving(true)
    setMessage(null)
    try {
      // TODO: PATCH /api/workspace/settings
      console.log('Update workspace settings:', data)
      setMessage({ type: 'success', text: 'Workspace settings updated' })
    } catch (err) {
      setMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to update settings',
      })
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6 p-6">
      {/* Workspace Info */}
      <div>
        <h3 className="mb-4 text-sm font-semibold">Workspace Settings</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
              Workspace Name
            </label>
            <input
              type="text"
              {...register('name', { required: 'Name is required' })}
              className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-stone-900 shadow-sm placeholder-stone-400 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
            />
            {errors.name && <p className="mt-1 text-xs text-red-500">{errors.name.message}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
              URL Slug
            </label>
            <input
              type="text"
              {...register('slug', { required: 'Slug is required' })}
              className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 font-mono text-sm text-stone-900 shadow-sm placeholder-stone-400 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
            />
            {errors.slug && <p className="mt-1 text-xs text-red-500">{errors.slug.message}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
              Description
            </label>
            <textarea
              {...register('description')}
              rows={3}
              className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-stone-900 shadow-sm placeholder-stone-400 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
            />
          </div>
        </div>
      </div>

      {/* Limits */}
      <div className="border-t border-stone-200 pt-6 dark:border-stone-700">
        <h3 className="mb-4 text-sm font-semibold">Workspace Limits</h3>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
              Max Team Members
            </label>
            <input
              type="number"
              {...register('max_team_members')}
              className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-stone-900 shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
            />
            <p className="mt-1 text-xs text-stone-500">Leave empty for unlimited</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
              Max Channels
            </label>
            <input
              type="number"
              {...register('max_channels')}
              className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-stone-900 shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
            />
            <p className="mt-1 text-xs text-stone-500">Leave empty for unlimited</p>
          </div>
        </div>
      </div>

      {/* Message */}
      {message && (
        <div
          className={`rounded-md p-3 text-sm ${
            message.type === 'success'
              ? 'border border-green-200 bg-green-50 text-green-800 dark:border-green-900 dark:bg-green-950 dark:text-green-200'
              : 'border border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200'
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Save Button */}
      <div className="border-t border-stone-200 pt-6 dark:border-stone-700">
        <button
          type="submit"
          disabled={isSaving}
          className="rounded bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
        >
          {isSaving ? 'Saving...' : 'Save Settings'}
        </button>
      </div>

      {/* Danger Zone */}
      <div className="border-t border-stone-200 pt-6 dark:border-stone-700">
        <h3 className="mb-4 text-sm font-semibold text-red-600 dark:text-red-400">Danger Zone</h3>
        <div className="space-y-3">
            <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-900 dark:bg-stone-900">
            <p className="text-sm font-medium text-red-900 dark:text-red-100">
              Delete this workspace
            </p>
            <p className="mt-1 text-xs text-red-700 dark:text-red-300">
              This action cannot be undone. All data will be permanently deleted.
            </p>
            <button
              type="button"
              className="mt-3 rounded bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700"
            >
              Delete Workspace
            </button>
          </div>
        </div>
      </div>
    </form>
  )
}
