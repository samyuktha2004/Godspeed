import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '@/lib/http'
import { useUIStore } from '@/stores/uiStore'
import type { Channel, CreateChannelInput, ChannelSensitivity } from '@/types/settings'
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton'
import { cn } from '@/lib/utils'

const SENSITIVITY_STYLES: Record<ChannelSensitivity, string> = {
  public:       'bg-green-100  text-green-800  dark:bg-green-900/30  dark:text-green-300',
  internal:     'bg-blue-100   text-blue-800   dark:bg-blue-900/30   dark:text-blue-300',
  confidential: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300',
  restricted:   'bg-red-100    text-red-800    dark:bg-red-900/30    dark:text-red-300',
}

const SENSITIVITY_LABELS: Record<ChannelSensitivity, string> = {
  public:       '🌐 Public',
  internal:     '🔒 Internal',
  confidential: '🔐 Confidential',
  restricted:   '🚫 Restricted',
}

const SENSITIVITY_HINTS: Record<ChannelSensitivity, string> = {
  public:       'Visible to all team members',
  internal:     'Team members only',
  confidential: 'Restricted to specified roles',
  restricted:   'Requires explicit per-user grant',
}

async function fetchChannels(): Promise<Channel[]> {
  const res  = await apiFetch('/api/admin/channels')
  const data = await res.json()
  return (data.channels ?? data) as Channel[]
}

async function createChannel(input: CreateChannelInput): Promise<Channel> {
  const res = await apiFetch('/api/admin/channels', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(input),
  })
  return res.json()
}

async function deleteChannel(id: string): Promise<void> {
  await apiFetch(`/api/admin/channels/${id}`, { method: 'DELETE' })
}

const INPUT_CLASS =
  'block w-full rounded border border-surface-subtle bg-white px-3 py-2 text-sm text-stone-900 placeholder-stone-400 focus:outline-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white'

export function AdminChannelManagement() {
  const qc       = useQueryClient()
  const addToast = useUIStore((s) => s.addToast)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<CreateChannelInput>({ name: '', sensitivity: 'internal' })

  const { data: channels = [], isLoading } = useQuery({
    queryKey: ['admin-channels'],
    queryFn:  fetchChannels,
    staleTime: 60_000,
  })

  const create = useMutation({
    mutationFn: createChannel,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-channels'] })
      setForm({ name: '', sensitivity: 'internal' })
      setShowForm(false)
      addToast({ type: 'success', message: 'Channel created' })
    },
    onError: () => addToast({ type: 'error', message: 'Failed to create channel' }),
  })

  const remove = useMutation({
    mutationFn: deleteChannel,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-channels'] })
      addToast({ type: 'success', message: 'Channel deleted' })
    },
    onError: () => addToast({ type: 'error', message: 'Failed to delete channel' }),
  })

  const handleCreate = () => {
    if (!form.name.trim()) return
    create.mutate(form)
  }

  return (
    <div className="flex flex-col gap-5 p-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium">Channels</p>
          <p className="text-xs text-stone-400">{channels.length} channel{channels.length !== 1 ? 's' : ''} · controls who can search which documents</p>
        </div>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-lg bg-brand px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-dark"
        >
          + Add channel
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <div className="flex flex-col gap-4 rounded-xl border border-brand/20 bg-brand/5 p-4 dark:bg-brand/10">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-stone-600 dark:text-stone-400">Channel name</label>
            <input
              type="text"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Engineering, HR, Finance"
              className={INPUT_CLASS}
            />
          </div>

          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-stone-600 dark:text-stone-400">Data source type (optional)</label>
            <select
              value={form.source_type ?? ''}
              onChange={(e) => setForm({ ...form, source_type: e.target.value || undefined })}
              className={INPUT_CLASS}
            >
              <option value="">General</option>
              <option value="github">GitHub</option>
              <option value="confluence">Confluence</option>
              <option value="jira">Jira</option>
              <option value="slack">Slack</option>
              <option value="file">File upload</option>
            </select>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-xs font-medium text-stone-600 dark:text-stone-400">Sensitivity</label>
            <div className="grid grid-cols-2 gap-2">
              {(Object.keys(SENSITIVITY_STYLES) as ChannelSensitivity[]).map((level) => (
                <button
                  key={level}
                  type="button"
                  onClick={() => setForm({ ...form, sensitivity: level })}
                  className={cn(
                    'rounded-lg border-2 px-3 py-2 text-left text-xs font-medium transition-colors',
                    form.sensitivity === level
                      ? `border-brand ${SENSITIVITY_STYLES[level]}`
                      : 'border-surface-subtle bg-white text-stone-600 hover:border-stone-300 dark:bg-stone-900 dark:text-stone-300',
                  )}
                >
                  <p>{SENSITIVITY_LABELS[level]}</p>
                  <p className="mt-0.5 font-normal opacity-70">{SENSITIVITY_HINTS[level]}</p>
                </button>
              ))}
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleCreate}
              disabled={create.isPending || !form.name.trim()}
              className="rounded-lg bg-brand px-4 py-1.5 text-xs font-medium text-white hover:bg-brand-dark disabled:opacity-60"
            >
              {create.isPending ? 'Creating…' : 'Create channel'}
            </button>
            <button
              onClick={() => setShowForm(false)}
              className="rounded-lg border border-surface-subtle px-4 py-1.5 text-xs font-medium text-stone-600 hover:bg-stone-50 dark:text-stone-300 dark:hover:bg-stone-800"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* List */}
      {isLoading ? (
        <LoadingSkeleton rows={4} />
      ) : channels.length === 0 ? (
        <div className="rounded-xl border-2 border-dashed border-surface-subtle py-12 text-center">
          <p className="text-sm text-stone-500">No channels yet.</p>
          <p className="mt-1 text-xs text-stone-400">
            Channels control which documents users can search. Start by adding one.
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {channels.map((ch) => (
            <div
              key={ch.id}
              className="flex items-center justify-between rounded-xl border border-surface-subtle p-4"
            >
              <div className="flex items-center gap-3">
                <div>
                  <p className="text-sm font-medium text-stone-900 dark:text-stone-100">{ch.name}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', SENSITIVITY_STYLES[ch.sensitivity])}>
                      {SENSITIVITY_LABELS[ch.sensitivity]}
                    </span>
                    {ch.source_type && (
                      <span className="text-xs text-stone-400">{ch.source_type}</span>
                    )}
                    <span className="text-xs text-stone-400">
                      Created {new Date(ch.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              </div>
              <button
                onClick={() => remove.mutate(ch.id)}
                disabled={remove.isPending}
                className="text-xs text-stone-400 hover:text-red-600 disabled:opacity-40"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
