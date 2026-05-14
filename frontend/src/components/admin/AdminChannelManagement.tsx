import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { apiFetch } from '@/lib/http'
import { Channel, CreateChannelInput, ChannelSensitivity } from '@/types/settings'
import { LoadingSkeleton } from '../common/LoadingSkeleton'

const SENSITIVITY_COLORS: Record<ChannelSensitivity, string> = {
  public: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
  internal: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  confidential: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
  restricted: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
}

const SENSITIVITY_ICONS: Record<ChannelSensitivity, string> = {
  public: '🌐',
  internal: '🔒',
  confidential: '🔐',
  restricted: '🚫',
}

export function AdminChannelManagement() {
  const [showAddForm, setShowAddForm] = useState(false)
  const [formData, setFormData] = useState<CreateChannelInput>({
    name: '',
    sensitivity: 'internal',
  })

  // Fetch channels
  const { data: channels, isLoading, refetch } = useQuery({
    queryKey: ['workspace-channels'],
    queryFn: async () => {
      // TODO: GET /api/workspace/channels
      return [] as Channel[]
    },
  })

  // Create channel
  const { mutate: createChannel, isPending: isCreating } = useMutation({
    mutationFn: async (input: CreateChannelInput) => {
      // TODO: POST /api/workspace/channels
      console.log('Create channel:', input)
    },
    onSuccess: () => {
      setFormData({ name: '', sensitivity: 'internal' })
      setShowAddForm(false)
      refetch()
    },
  })

  const handleCreateChannel = () => {
    if (!formData.name.trim()) return
    createChannel(formData)
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold">Channels</h3>
          <p className="mt-1 text-xs text-stone-500">{channels?.length || 0} channels total</p>
        </div>
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="rounded bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-dark"
        >
          + Add Channel
        </button>
      </div>

      {/* Create Channel Form */}
      {showAddForm && (
        <div className="space-y-4 rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-900 dark:bg-stone-900">
          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
              Channel Name
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="e.g., Engineering, HR, Finance"
              className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-stone-900 placeholder-stone-400 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
              Data Source Type (Optional)
            </label>
            <select
              value={formData.source_type || ''}
              onChange={(e) => setFormData({ ...formData, source_type: e.target.value || undefined })}
              className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-stone-900 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
            >
              <option value="">General</option>
              <option value="github">GitHub</option>
              <option value="confluence">Confluence</option>
              <option value="jira">Jira</option>
              <option value="notion">Notion</option>
              <option value="slack">Slack</option>
              <option value="file">File Upload</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
              Sensitivity Level
            </label>
            <div className="mt-2 grid grid-cols-2 gap-2">
              {(Object.keys(SENSITIVITY_COLORS) as ChannelSensitivity[]).map((level) => (
                <button
                  key={level}
                  onClick={() => setFormData({ ...formData, sensitivity: level })}
                  className={`rounded border-2 px-3 py-2 text-left text-sm font-medium transition-colors ${
                    formData.sensitivity === level
                      ? `border-brand ${SENSITIVITY_COLORS[level]}`
                      : 'border-stone-300 text-stone-700 hover:border-stone-400 dark:border-stone-600 dark:text-stone-300'
                  }`}
                >
                  <span className="mr-2">{SENSITIVITY_ICONS[level]}</span>
                  {level.charAt(0).toUpperCase() + level.slice(1)}
                </button>
              ))}
            </div>
            <p className="mt-2 text-xs text-stone-500">
              • Public: visible to all • Internal: team members only • Confidential: executives only • Restricted: need approval
            </p>
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleCreateChannel}
              disabled={isCreating || !formData.name.trim()}
              className="rounded bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
            >
              {isCreating ? 'Creating...' : 'Create Channel'}
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

      {/* Channels List */}
      <div>
        {isLoading ? (
          <LoadingSkeleton rows={4} className="h-16" />
        ) : channels && channels.length > 0 ? (
          <div className="grid gap-3">
            {channels.map((channel) => (
              <div
                key={channel.id}
                className="flex items-start justify-between rounded-lg border border-stone-200 p-4 dark:border-stone-700"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h4 className="font-medium text-stone-900 dark:text-white">{channel.name}</h4>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        SENSITIVITY_COLORS[channel.sensitivity]
                      }`}
                    >
                      {SENSITIVITY_ICONS[channel.sensitivity]} {channel.sensitivity}
                    </span>
                  </div>
                  <div className="mt-2 flex gap-3 text-xs text-stone-600 dark:text-stone-400">
                    {channel.source_type && <span>📁 {channel.source_type}</span>}
                    <span>Created {new Date(channel.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button className="text-xs font-medium text-stone-500 hover:text-brand">
                    Edit
                  </button>
                  <button className="text-xs font-medium text-stone-500 hover:text-red-600">
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border-2 border-dashed border-stone-300 p-8 text-center dark:border-stone-600">
            <p className="text-sm text-stone-500">No channels yet</p>
            <p className="mt-1 text-xs text-stone-400">
              Create your first channel to organize data by team or department
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
