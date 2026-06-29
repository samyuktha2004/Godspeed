import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '@/lib/http'
import { useAuth } from '@/hooks/useAuth'
import { useUIStore } from '@/stores/uiStore'
import { cn } from '@/lib/utils'
import { Tabs, TabPanel } from '@/components/common/Tabs'
import { LoadingSkeleton } from '@/components/common/LoadingSkeleton'
import type { Channel, ChannelSensitivity } from '@/types/settings'

// ─── Types ───────────────────────────────────────────────────────────────────

interface TeamMember {
  id:        string
  email:     string
  name:      string
  role:      string
  is_active: boolean
}

interface Signal {
  id:          string
  signal_type: string
  severity:    'critical' | 'high' | 'medium' | 'low'
  score:       number
  team_id:     string | null
  resolved:    boolean
  detected_at: string
  details:     Record<string, unknown>
}

// ─── Constants ───────────────────────────────────────────────────────────────

const SENSITIVITY_STYLES: Record<ChannelSensitivity, string> = {
  public:       'bg-green-100  text-green-800  dark:bg-green-900/30  dark:text-green-300',
  internal:     'bg-blue-100   text-blue-800   dark:bg-blue-900/30   dark:text-blue-300',
  confidential: 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300',
  restricted:   'bg-red-100    text-red-800    dark:bg-red-900/30    dark:text-red-300',
}

const SENSITIVITY_LABELS: Record<ChannelSensitivity, string> = {
  public:       'Public',
  internal:     'Internal',
  confidential: 'Confidential',
  restricted:   'Restricted',
}

const SEVERITY_STYLES: Record<Signal['severity'], string> = {
  critical: 'bg-red-100    text-red-800    dark:bg-red-900/30    dark:text-red-300',
  high:     'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300',
  medium:   'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
  low:      'bg-stone-100  text-stone-600  dark:bg-stone-800     dark:text-stone-400',
}

type Tab = 'members' | 'channels' | 'signals'

const TABS = [
  { id: 'members'  as const, label: 'Members'  },
  { id: 'channels' as const, label: 'Channels' },
  { id: 'signals'  as const, label: 'Signals'  },
]

// ─── Members tab ─────────────────────────────────────────────────────────────

function MembersTab() {
  const qc       = useQueryClient()
  const addToast = useUIStore((s) => s.addToast)
  const [showInvite, setShowInvite] = useState(false)
  const [inviteForm, setInviteForm] = useState({ email: '', name: '' })
  const [inviteLink, setInviteLink] = useState<{ url: string; emailSent: boolean } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['team-members'],
    queryFn:  async () => {
      const res  = await apiFetch('/api/workspace/users')
      const json = await res.json()
      return (json.users ?? []) as TeamMember[]
    },
  })
  const members = data ?? []

  const { mutate: sendInvite, isPending: isSending } = useMutation({
    mutationFn: async () => {
      const res = await apiFetch('/api/auth/invite', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ email: inviteForm.email, name: inviteForm.name, role: 'engineer' }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error((body as { detail?: string }).detail ?? `Error ${res.status}`)
      }
      return res.json() as Promise<{ ok: boolean; invite_url: string; email_sent: boolean }>
    },
    onSuccess: (data) => {
      setInviteForm({ email: '', name: '' })
      setError(null)
      setInviteLink({ url: data.invite_url, emailSent: data.email_sent })
      qc.invalidateQueries({ queryKey: ['team-members'] })
    },
    onError: (err: Error) => {
      addToast({ type: 'error', message: err.message })
      setError(err.message)
    },
  })

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <p className="text-xs text-stone-400">{members.length} member{members.length !== 1 ? 's' : ''} on your team</p>
        <button
          onClick={() => { setShowInvite((v) => !v); setInviteLink(null); setError(null) }}
          className="rounded bg-brand px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-dark"
        >
          + Invite Engineer
        </button>
      </div>

      {showInvite && (
        <div className="space-y-3 rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-900 dark:bg-stone-900">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="block text-xs font-medium text-stone-700 dark:text-stone-300">Name</label>
              <input
                type="text"
                value={inviteForm.name}
                onChange={(e) => setInviteForm({ ...inviteForm, name: e.target.value })}
                placeholder="Jane Smith"
                className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-sm placeholder-stone-400 focus:border-brand focus:outline-none dark:border-stone-600 dark:bg-stone-800 dark:text-white"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-stone-700 dark:text-stone-300">Email</label>
              <input
                type="email"
                value={inviteForm.email}
                onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })}
                placeholder="jane@company.com"
                className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-sm placeholder-stone-400 focus:border-brand focus:outline-none dark:border-stone-600 dark:bg-stone-800 dark:text-white"
              />
            </div>
          </div>

          {error && (
            <p className="rounded bg-red-100 px-3 py-2 text-xs text-red-700 dark:bg-red-900/30 dark:text-red-400">{error}</p>
          )}

          <div className="flex gap-2">
            <button
              onClick={() => sendInvite()}
              disabled={isSending || !inviteForm.email.trim() || !inviteForm.name.trim()}
              className="rounded bg-brand px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-dark disabled:opacity-50"
            >
              {isSending ? 'Sending…' : 'Send Invite'}
            </button>
            <button
              onClick={() => { setShowInvite(false); setInviteLink(null); setError(null) }}
              className="rounded border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 hover:bg-stone-100 dark:border-stone-600 dark:text-stone-300 dark:hover:bg-stone-700"
            >
              Cancel
            </button>
          </div>

          {inviteLink && (
            <div className="rounded-lg border border-green-200 bg-green-50 p-3 dark:border-green-800 dark:bg-green-950/30">
              <p className="mb-1 text-xs font-medium text-green-800 dark:text-green-300">
                {inviteLink.emailSent ? 'Invite sent! Share this link as backup:' : 'Share this link directly:'}
              </p>
              <div className="flex items-center gap-2">
                <input
                  readOnly
                  value={inviteLink.url}
                  className="flex-1 rounded border border-green-300 bg-white px-2 py-1.5 font-mono text-xs text-stone-800 dark:border-green-700 dark:bg-stone-800 dark:text-stone-200"
                />
                <button
                  onClick={() => navigator.clipboard.writeText(inviteLink.url)}
                  className="rounded border border-green-300 px-2 py-1.5 text-xs font-medium text-green-700 hover:bg-green-100 dark:border-green-700 dark:text-green-400"
                >
                  Copy
                </button>
              </div>
              <p className="mt-1 text-xs text-green-700 dark:text-green-400">Expires in 7 days.</p>
            </div>
          )}
        </div>
      )}

      {isLoading ? (
        <LoadingSkeleton rows={4} />
      ) : members.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-stone-300 p-8 text-center dark:border-stone-600">
          <p className="text-sm text-stone-500">No team members yet</p>
          <p className="mt-1 text-xs text-stone-400">Invite engineers to your team using the button above</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-stone-200 dark:border-stone-700">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-stone-200 bg-stone-50 dark:border-stone-700 dark:bg-stone-800">
              <tr>
                <th className="px-4 py-2 font-semibold text-stone-700 dark:text-stone-300">Name</th>
                <th className="px-4 py-2 font-semibold text-stone-700 dark:text-stone-300">Email</th>
                <th className="px-4 py-2 font-semibold text-stone-700 dark:text-stone-300">Role</th>
                <th className="px-4 py-2 font-semibold text-stone-700 dark:text-stone-300">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-200 dark:divide-stone-700">
              {members.map((m) => (
                <tr key={m.id} className="hover:bg-stone-50 dark:hover:bg-stone-800">
                  <td className="px-4 py-3 font-medium text-stone-900 dark:text-white">{m.name}</td>
                  <td className="px-4 py-3 text-stone-600 dark:text-stone-400">{m.email}</td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-stone-200 px-2 py-0.5 text-xs font-medium text-stone-700 dark:bg-stone-700 dark:text-stone-300">
                      {m.role}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', m.is_active
                      ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                      : 'bg-stone-100 text-stone-500 dark:bg-stone-700 dark:text-stone-400'
                    )}>
                      {m.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// ─── Channels tab ─────────────────────────────────────────────────────────────

function ChannelsTab() {
  const qc       = useQueryClient()
  const addToast = useUIStore((s) => s.addToast)
  const [editing, setEditing] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<{ name: string; sensitivity: ChannelSensitivity }>({ name: '', sensitivity: 'internal' })

  const { data, isLoading } = useQuery({
    queryKey: ['team-channels'],
    queryFn:  async () => {
      const res  = await apiFetch('/api/workspace/channels')
      const json = await res.json()
      return (json.channels ?? []) as Channel[]
    },
  })
  const channels = data ?? []

  const patchChannel = useMutation({
    mutationFn: async ({ id, updates }: { id: string; updates: Partial<Channel> }) => {
      const res = await apiFetch(`/api/workspace/channels/${id}`, {
        method:  'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(updates),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error((body as { detail?: string }).detail ?? `Error ${res.status}`)
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['team-channels'] })
      setEditing(null)
      addToast({ type: 'success', message: 'Channel updated' })
    },
    onError: (err: Error) => addToast({ type: 'error', message: err.message }),
  })

  const startEdit = (ch: Channel) => {
    setEditing(ch.id)
    setEditForm({ name: ch.name, sensitivity: ch.sensitivity })
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-stone-400">
        {channels.length} channel{channels.length !== 1 ? 's' : ''} assigned to your team · contact an admin to create or delete channels
      </p>

      {isLoading ? (
        <LoadingSkeleton rows={3} />
      ) : channels.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-stone-300 p-8 text-center dark:border-stone-600">
          <p className="text-sm text-stone-500">No channels for your team yet</p>
          <p className="mt-1 text-xs text-stone-400">Ask an admin to create channels and assign them to your team</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {channels.map((ch) => (
            <div key={ch.id} className="rounded-xl border border-surface-subtle p-4">
              {editing === ch.id ? (
                <div className="space-y-3">
                  <input
                    type="text"
                    value={editForm.name}
                    onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                    className="block w-full rounded border border-stone-300 bg-white px-3 py-2 text-sm focus:border-brand focus:outline-none dark:border-stone-600 dark:bg-stone-800 dark:text-white"
                  />
                  <div className="flex flex-wrap gap-2">
                    {(Object.keys(SENSITIVITY_LABELS) as ChannelSensitivity[]).map((level) => (
                      <button
                        key={level}
                        type="button"
                        onClick={() => setEditForm({ ...editForm, sensitivity: level })}
                        className={cn(
                          'rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                          editForm.sensitivity === level
                            ? `border-brand ${SENSITIVITY_STYLES[level]}`
                            : 'border-surface-subtle bg-white text-stone-500 hover:border-stone-300 dark:bg-stone-900',
                        )}
                      >
                        {SENSITIVITY_LABELS[level]}
                      </button>
                    ))}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => patchChannel.mutate({ id: ch.id, updates: editForm })}
                      disabled={patchChannel.isPending || !editForm.name.trim()}
                      className="rounded bg-brand px-3 py-1.5 text-xs font-medium text-white hover:bg-brand-dark disabled:opacity-50"
                    >
                      {patchChannel.isPending ? 'Saving…' : 'Save'}
                    </button>
                    <button
                      onClick={() => setEditing(null)}
                      className="rounded border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-600 hover:bg-stone-50 dark:border-stone-600 dark:text-stone-300"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-stone-900 dark:text-stone-100">{ch.name}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', SENSITIVITY_STYLES[ch.sensitivity])}>
                        {SENSITIVITY_LABELS[ch.sensitivity]}
                      </span>
                      {ch.source_type && (
                        <span className="text-xs text-stone-400">{ch.source_type}</span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={() => startEdit(ch)}
                    className="text-xs font-medium text-stone-400 hover:text-brand"
                  >
                    Edit
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Signals tab ──────────────────────────────────────────────────────────────

function SignalsTab() {
  const qc       = useQueryClient()
  const addToast = useUIStore((s) => s.addToast)

  const { data, isLoading } = useQuery({
    queryKey: ['team-signals'],
    queryFn:  async () => {
      const res  = await apiFetch('/api/anomaly/signals?resolved=false&limit=50')
      const json = await res.json()
      return (json.signals ?? []) as Signal[]
    },
  })
  const signals = data ?? []

  const resolve = useMutation({
    mutationFn: async (signalId: string) => {
      const res = await apiFetch(`/api/anomaly/signals/${signalId}/resolve`, { method: 'PATCH' })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error((body as { detail?: string }).detail ?? `Error ${res.status}`)
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['team-signals'] })
      addToast({ type: 'success', message: 'Signal resolved' })
    },
    onError: (err: Error) => addToast({ type: 'error', message: err.message }),
  })

  return (
    <div className="space-y-4">
      <p className="text-xs text-stone-400">
        {signals.length} unresolved signal{signals.length !== 1 ? 's' : ''} for your team
      </p>

      {isLoading ? (
        <LoadingSkeleton rows={4} />
      ) : signals.length === 0 ? (
        <div className="rounded-lg border-2 border-dashed border-stone-300 p-8 text-center dark:border-stone-600">
          <p className="text-sm text-stone-500">No active signals</p>
          <p className="mt-1 text-xs text-stone-400">Your team has no unresolved anomalies right now</p>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {signals.map((sig) => (
            <div key={sig.id} className="flex items-start justify-between rounded-xl border border-surface-subtle p-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className={cn('rounded-full px-2 py-0.5 text-xs font-medium', SEVERITY_STYLES[sig.severity])}>
                    {sig.severity}
                  </span>
                  <span className="text-sm font-medium text-stone-900 dark:text-stone-100">
                    {sig.signal_type.replace(/_/g, ' ')}
                  </span>
                </div>
                <p className="text-xs text-stone-400">
                  Score {sig.score.toFixed(2)} · Detected {new Date(sig.detected_at).toLocaleString()}
                </p>
              </div>
              <button
                onClick={() => resolve.mutate(sig.id)}
                disabled={resolve.isPending}
                className="ml-4 shrink-0 rounded border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-600 hover:border-green-400 hover:text-green-700 disabled:opacity-40 dark:border-stone-600 dark:text-stone-400"
              >
                Resolve
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Root ─────────────────────────────────────────────────────────────────────

export function ManagerTeamView() {
  const { user } = useAuth()
  const [tab, setTab] = useState<Tab>('members')

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold">My Team</h1>
        {user?.team_id && (
          <p className="mt-1 text-sm text-stone-500">Team · {user.team_id}</p>
        )}
      </div>

      <Tabs tabs={TABS} active={tab} onChange={setTab} className="mb-6" />

      <TabPanel id="members" active={tab}>
        <MembersTab />
      </TabPanel>

      <TabPanel id="channels" active={tab}>
        <ChannelsTab />
      </TabPanel>

      <TabPanel id="signals" active={tab}>
        <SignalsTab />
      </TabPanel>
    </div>
  )
}
