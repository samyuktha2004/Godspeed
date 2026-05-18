import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiFetch } from '@/lib/http'
import { UserInvite } from '@/types/settings'
import { LoadingSkeleton } from '../common/LoadingSkeleton'

interface WorkspaceUser {
  id: string
  email: string
  name: string
  role: string
  is_active: boolean
}

export function AdminUserManagement() {
  const qc = useQueryClient()
  const [showAddForm, setShowAddForm] = useState(false)
  const [formData, setFormData] = useState<UserInvite>({ email: '', name: '', role: 'engineer' })
  const [inviteLink, setInviteLink] = useState<{ url: string; emailSent: boolean } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['workspace-users'],
    queryFn: async () => {
      const res = await apiFetch('/api/workspace/users')
      const json = await res.json()
      return (json.users ?? []) as WorkspaceUser[]
    },
  })
  const users = data ?? []

  const { mutate: sendInvite, isPending: isSending } = useMutation({
    mutationFn: async (input: UserInvite) => {
      const res = await apiFetch('/api/auth/invite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: input.email, name: input.name, role: input.role }),
      })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body.detail ?? `Error ${res.status}`)
      }
      return res.json() as Promise<{ ok: boolean; email: string; invite_url: string; email_sent: boolean }>
    },
    onSuccess: (data) => {
      setFormData({ email: '', name: '', role: 'engineer' })
      setError(null)
      setInviteLink({ url: data.invite_url, emailSent: data.email_sent })
      qc.invalidateQueries({ queryKey: ['workspace-users'] })
    },
    onError: (err: Error) => {
      setError(err.message)
    },
  })

  const { mutate: removeUser } = useMutation({
    mutationFn: async (userId: string) => {
      const res = await apiFetch(`/api/workspace/users/${userId}`, { method: 'DELETE' })
      if (!res.ok) throw new Error(`Error ${res.status}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['workspace-users'] }),
  })

  const handleInvite = () => {
    if (!formData.email.trim() || !formData.name.trim()) return
    setError(null)
    setInviteLink(null as null)
    sendInvite(formData)
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold">Workspace Users</h3>
          <p className="mt-1 text-xs text-stone-500">{users.length} user{users.length !== 1 ? 's' : ''}</p>
        </div>
        <button
          onClick={() => { setShowAddForm(!showAddForm); setInviteLink(null as null); setError(null) }}
          className="rounded bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-dark"
        >
          + Invite User
        </button>
      </div>

      {/* Invite Form */}
      {showAddForm && (
        <div className="space-y-4 rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-900 dark:bg-stone-900">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div>
              <label className="block text-xs font-medium text-stone-700 dark:text-stone-300">Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Jane Smith"
                className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 placeholder-stone-400 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-stone-700 dark:text-stone-300">Email</label>
              <input
                type="email"
                value={formData.email}
                onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                placeholder="jane@company.com"
                className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 placeholder-stone-400 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-stone-700 dark:text-stone-300">Role</label>
              <select
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value as UserInvite['role'] })}
                className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
              >
                <option value="engineer">Engineer</option>
                <option value="manager">Manager</option>
                <option value="admin">Admin</option>
                <option value="org_admin">Org Admin</option>
              </select>
            </div>
          </div>

          {error && (
            <p className="rounded bg-red-100 px-3 py-2 text-xs text-red-700 dark:bg-red-900/30 dark:text-red-400">
              {error}
            </p>
          )}

          <div className="flex gap-2">
            <button
              onClick={handleInvite}
              disabled={isSending || !formData.email.trim() || !formData.name.trim()}
              className="rounded bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
            >
              {isSending ? 'Sending...' : 'Send Invite'}
            </button>
            <button
              onClick={() => { setShowAddForm(false); setInviteLink(null as null); setError(null) }}
              className="rounded border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 hover:bg-stone-100 dark:border-stone-600 dark:text-stone-300 dark:hover:bg-stone-700"
            >
              Cancel
            </button>
          </div>

          {inviteLink && (
            <div className="rounded-lg border border-green-200 bg-green-50 p-3 dark:border-green-800 dark:bg-green-950/30">
              <p className="mb-1 text-xs font-medium text-green-800 dark:text-green-300">
                {inviteLink.emailSent
                  ? 'Invite email sent! Share the link below as backup:'
                  : 'Email not configured — share this link directly with the user:'}
              </p>
              <div className="flex items-center gap-2">
                <input
                  readOnly
                  value={inviteLink.url}
                  className="flex-1 rounded border border-green-300 bg-white px-2 py-1.5 text-xs font-mono text-stone-800 dark:border-green-700 dark:bg-stone-800 dark:text-stone-200"
                />
                <button
                  onClick={() => navigator.clipboard.writeText(inviteLink.url)}
                  className="rounded border border-green-300 px-2 py-1.5 text-xs font-medium text-green-700 hover:bg-green-100 dark:border-green-700 dark:text-green-400 dark:hover:bg-green-900/40"
                >
                  Copy
                </button>
              </div>
              <p className="mt-1 text-xs text-green-700 dark:text-green-400">Expires in 7 days.</p>
            </div>
          )}
        </div>
      )}

      {/* Users Table */}
      <div>
        {isLoading ? (
          <LoadingSkeleton rows={5} className="h-10" />
        ) : users.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border border-stone-200 dark:border-stone-700">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-stone-200 bg-stone-50 dark:border-stone-700 dark:bg-stone-800">
                <tr>
                  <th className="px-4 py-2 font-semibold text-stone-700 dark:text-stone-300">Name</th>
                  <th className="px-4 py-2 font-semibold text-stone-700 dark:text-stone-300">Email</th>
                  <th className="px-4 py-2 font-semibold text-stone-700 dark:text-stone-300">Role</th>
                  <th className="px-4 py-2 font-semibold text-stone-700 dark:text-stone-300">Status</th>
                  <th className="px-4 py-2 text-right font-semibold text-stone-700 dark:text-stone-300">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-200 dark:divide-stone-700">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-stone-50 dark:hover:bg-stone-800">
                    <td className="px-4 py-3 font-medium text-stone-900 dark:text-white">{u.name}</td>
                    <td className="px-4 py-3 text-stone-600 dark:text-stone-400">{u.email}</td>
                    <td className="px-4 py-3">
                      <span className="rounded-full bg-stone-200 px-2 py-0.5 text-xs font-medium text-stone-700 dark:bg-stone-700 dark:text-stone-300">
                        {u.role}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        u.is_active
                          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                          : 'bg-stone-100 text-stone-500 dark:bg-stone-700 dark:text-stone-400'
                      }`}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => {
                          if (confirm(`Remove ${u.name} from workspace?`)) removeUser(u.id)
                        }}
                        className="text-xs font-medium text-stone-500 hover:text-red-600"
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="rounded-lg border-2 border-dashed border-stone-300 p-6 text-center dark:border-stone-600">
            <p className="text-sm text-stone-500">No users yet</p>
            <p className="mt-1 text-xs text-stone-400">Click "Invite User" to add your first team member</p>
          </div>
        )}
      </div>
    </div>
  )
}
