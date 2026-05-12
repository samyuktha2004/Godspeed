import { useState, useRef } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { apiFetch } from '@/lib/http'
import { UserInvite, BulkUserImport } from '@/types/settings'
import { User } from '@/types/user'
import { LoadingSkeleton } from '../common/LoadingSkeleton'

export function AdminUserManagement() {
  const [showAddForm, setShowAddForm] = useState(false)
  const [showBulkImport, setShowBulkImport] = useState(false)
  const [formData, setFormData] = useState<UserInvite>({
    email: '',
    name: '',
    role: 'engineer',
  })
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Fetch users
  const { data: users, isLoading, refetch } = useQuery({
    queryKey: ['workspace-users'],
    queryFn: async () => {
      // TODO: GET /api/workspace/users
      return [] as User[]
    },
  })

  // Add single user
  const { mutate: addUser, isPending: isAddingUser } = useMutation({
    mutationFn: async (input: UserInvite) => {
      // TODO: POST /api/workspace/users (send invitation)
      console.log('Add user:', input)
    },
    onSuccess: () => {
      setFormData({ email: '', name: '', role: 'engineer' })
      setShowAddForm(false)
      refetch()
    },
  })

  // Bulk import users
  const { mutate: bulkImport, isPending: isImporting } = useMutation({
    mutationFn: async (file: File) => {
      // TODO: POST /api/workspace/users/bulk-import with CSV/Excel parsing
      console.log('Bulk import file:', file)
      // For now, mock parsing
      return { count: 0 } as { count: number }
    },
    onSuccess: () => {
      setShowBulkImport(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
      refetch()
    },
  })

  const handleAddUser = () => {
    if (!formData.email.trim() || !formData.name.trim()) return
    addUser(formData)
  }

  const handleBulkImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.currentTarget.files?.[0]
    if (file) {
      bulkImport(file)
    }
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header with Actions */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold">Workspace Users</h3>
          <p className="mt-1 text-xs text-stone-500">{users?.length || 0} users total</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="rounded bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-dark"
          >
            + Add User
          </button>
          <button
            onClick={() => setShowBulkImport(!showBulkImport)}
            className="rounded border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 hover:bg-stone-50 dark:border-stone-600 dark:text-stone-300 dark:hover:bg-stone-800"
          >
            📥 Import CSV
          </button>
        </div>
      </div>

      {/* Add User Form */}
      {showAddForm && (
        <div className="space-y-4 rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-900 dark:bg-stone-900">
          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
              Name
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="John Doe"
              className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-stone-900 placeholder-stone-400 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
              Email
            </label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              placeholder="john@example.com"
              className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-stone-900 placeholder-stone-400 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
              Role
            </label>
            <select
              value={formData.role}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  role: e.target.value as 'engineer' | 'manager' | 'admin',
                })
              }
              className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-stone-900 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
            >
              <option value="engineer">Engineer</option>
              <option value="manager">Manager</option>
              <option value="admin">Admin</option>
            </select>
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleAddUser}
              disabled={isAddingUser || !formData.email.trim() || !formData.name.trim()}
              className="rounded bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
            >
              {isAddingUser ? 'Adding...' : 'Add User'}
            </button>
            <button
              onClick={() => setShowAddForm(false)}
              className="rounded border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 hover:bg-stone-100 dark:border-stone-600 dark:text-stone-300 dark:hover:bg-stone-700"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Bulk Import Form */}
      {showBulkImport && (
        <div className="space-y-4 rounded-lg border border-green-200 bg-green-50 p-4 dark:border-green-900 dark:bg-stone-900">
          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
              Upload CSV or Excel file
            </label>
            <p className="mt-1 text-xs text-stone-600 dark:text-stone-400">
              Format: name, email, role (engineer|manager|admin)
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={handleBulkImport}
              disabled={isImporting}
              className="mt-2 block w-full text-sm text-stone-500 file:rounded file:border-0 file:bg-brand file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-brand-dark dark:text-stone-400"
            />
          </div>
          <button
            onClick={() => setShowBulkImport(false)}
            className="rounded border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 hover:bg-stone-100 dark:border-stone-600 dark:text-stone-300 dark:hover:bg-stone-700"
          >
            Cancel
          </button>
        </div>
      )}

      {/* Users List */}
      <div>
        <h4 className="mb-3 text-sm font-semibold">Active Users</h4>
        {isLoading ? (
          <LoadingSkeleton count={5} height="h-10" />
        ) : users && users.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border border-stone-200 dark:border-stone-700">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-stone-200 bg-stone-50 dark:border-stone-700 dark:bg-stone-800">
                <tr>
                  <th className="px-4 py-2 font-semibold text-stone-700 dark:text-stone-300">Name</th>
                  <th className="px-4 py-2 font-semibold text-stone-700 dark:text-stone-300">Email</th>
                  <th className="px-4 py-2 font-semibold text-stone-700 dark:text-stone-300">Role</th>
                  <th className="px-4 py-2 font-semibold text-stone-700 dark:text-stone-300">Team</th>
                  <th className="px-4 py-2 text-right font-semibold text-stone-700 dark:text-stone-300">
                    Actions
                  </th>
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
                    <td className="px-4 py-3 text-stone-600 dark:text-stone-400">{u.team?.name || '—'}</td>
                    <td className="px-4 py-3 text-right">
                      <button className="text-xs font-medium text-stone-500 hover:text-red-600">
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
            <p className="mt-1 text-xs text-stone-400">Add your first user to get started</p>
          </div>
        )}
      </div>
    </div>
  )
}
