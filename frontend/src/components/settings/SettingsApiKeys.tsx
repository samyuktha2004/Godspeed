import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { apiFetch } from '@/lib/http'
import { ApiKey, ApiKeyProvider, CreateApiKeyInput } from '@/types/settings'
import { LoadingSkeleton } from '../common/LoadingSkeleton'

const PROVIDERS: { value: ApiKeyProvider; label: string; icon: string }[] = [
  { value: 'github', label: 'GitHub', icon: '🐙' },
  { value: 'openai', label: 'OpenAI', icon: '✨' },
  { value: 'claude', label: 'Claude', icon: '🤖' },
  { value: 'custom', label: 'Custom / Other', icon: '🔧' },
]

export function SettingsApiKeys() {
  const [showForm, setShowForm] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState<ApiKeyProvider>('github')
  const [keyName, setKeyName] = useState('')
  const [keySecret, setKeySecret] = useState('')
  const [revokeConfirm, setRevokeConfirm] = useState<string | null>(null)

  // Fetch API keys
  const { data: keys, isLoading, refetch } = useQuery({
    queryKey: ['api-keys'],
    queryFn: async () => {
      // TODO: Replace with actual endpoint once backend is built
      return [] as ApiKey[]
    },
  })

  // Create API key
  const { mutate: createKey, isPending: isCreating } = useMutation({
    mutationFn: async (input: CreateApiKeyInput) => {
      // TODO: POST /api/settings/api-keys
      console.log('Create API key:', input)
      return { id: 'new-key', ...input } as ApiKey
    },
    onSuccess: () => {
      setShowForm(false)
      setKeyName('')
      setKeySecret('')
      refetch()
    },
  })

  // Revoke API key
  const { mutate: revokeKey, isPending: isRevoking } = useMutation({
    mutationFn: async (id: string) => {
      // TODO: DELETE /api/settings/api-keys/{id}
      console.log('Revoke API key:', id)
    },
    onSuccess: () => {
      setRevokeConfirm(null)
      refetch()
    },
  })

  const handleCreateKey = () => {
    if (!keyName.trim() || !keySecret.trim()) {
      return
    }
    createKey({ provider: selectedProvider, name: keyName, secret: keySecret })
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold">API Keys</h3>
            <p className="mt-1 text-xs text-stone-500">
              Connect to external API providers (GitHub, OpenAI, Claude, etc.)
            </p>
          </div>
          <button
            onClick={() => setShowForm(!showForm)}
            className="rounded bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-dark"
          >
            {showForm ? '✕ Cancel' : '+ Add Key'}
          </button>
        </div>

        {/* Add Key Form */}
        {showForm && (
          <div className="mb-6 space-y-4 rounded-lg border border-blue-200 bg-blue-50 p-4 dark:border-blue-900 dark:bg-stone-900">
            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
                Provider
              </label>
              <div className="mt-2 grid grid-cols-2 gap-2">
                {PROVIDERS.map((p) => (
                  <button
                    key={p.value}
                    onClick={() => setSelectedProvider(p.value)}
                    className={`rounded border-2 px-3 py-2 text-left text-sm font-medium transition-colors ${
                      selectedProvider === p.value
                        ? 'border-brand bg-blue-100 text-brand dark:bg-blue-900'
                        : 'border-stone-300 text-stone-700 hover:border-stone-400 dark:border-stone-600 dark:text-stone-300'
                    }`}
                  >
                    <span className="mr-2">{p.icon}</span>
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
                Name (e.g., "My GitHub Token")
              </label>
              <input
                type="text"
                value={keyName}
                onChange={(e) => setKeyName(e.target.value)}
                placeholder="My API Key"
                className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-stone-900 placeholder-stone-400 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white dark:placeholder-stone-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
                Secret Key / Token
              </label>
              <textarea
                value={keySecret}
                onChange={(e) => setKeySecret(e.target.value)}
                placeholder="Paste your API key here. It will be encrypted in our database."
                rows={3}
                className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 font-mono text-xs text-stone-900 placeholder-stone-400 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white dark:placeholder-stone-500"
              />
              <p className="mt-1 text-xs text-stone-500">
                🔒 Your secret is encrypted and never shown again. Store it securely.
              </p>
            </div>

            <div className="flex gap-2">
              <button
                onClick={handleCreateKey}
                disabled={isCreating || !keyName.trim() || !keySecret.trim()}
                className="rounded bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
              >
                {isCreating ? 'Adding...' : 'Add Key'}
              </button>
              <button
                onClick={() => {
                  setShowForm(false)
                  setKeyName('')
                  setKeySecret('')
                }}
                className="rounded border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 hover:bg-stone-50 dark:border-stone-600 dark:text-stone-300 dark:hover:bg-stone-800"
              >
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Keys List */}
      <div>
        <h4 className="mb-3 text-sm font-semibold">Connected Keys</h4>
        {isLoading ? (
          <LoadingSkeleton count={3} height="h-12" />
        ) : keys && keys.length > 0 ? (
          <div className="space-y-2">
            {keys.map((key) => (
              <div
                key={key.id}
                className="flex items-center justify-between rounded-lg border border-stone-200 bg-stone-50 p-3 dark:border-stone-700 dark:bg-stone-800"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-stone-900 dark:text-white">
                      {key.name}
                    </span>
                    <span className="rounded bg-stone-200 px-2 py-0.5 text-xs text-stone-700 dark:bg-stone-700 dark:text-stone-300">
                      {key.provider}
                    </span>
                    {key.is_active && (
                      <span className="rounded bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900 dark:text-green-200">
                        Active
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-xs text-stone-500 dark:text-stone-400">
                    Added {new Date(key.created_at).toLocaleDateString()}
                    {key.last_used_at && ` • Last used ${new Date(key.last_used_at).toLocaleDateString()}`}
                  </p>
                </div>

                {/* Revoke Button */}
                {revokeConfirm === key.id ? (
                  <div className="flex gap-2">
                    <button
                      onClick={() => revokeKey(key.id)}
                      disabled={isRevoking}
                      className="rounded bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
                    >
                      {isRevoking ? '...' : 'Revoke'}
                    </button>
                    <button
                      onClick={() => setRevokeConfirm(null)}
                      className="rounded border border-stone-300 px-2 py-1 text-xs font-medium text-stone-700 hover:bg-stone-100 dark:border-stone-600 dark:text-stone-300 dark:hover:bg-stone-700"
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={() => setRevokeConfirm(key.id)}
                    className="text-xs font-medium text-red-600 hover:underline dark:text-red-400"
                  >
                    Revoke
                  </button>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-lg border-2 border-dashed border-stone-300 p-6 text-center dark:border-stone-600">
            <p className="text-sm text-stone-500">No API keys added yet</p>
            <p className="mt-1 text-xs text-stone-400">
              Add your first key to connect to external providers
            </p>
          </div>
        )}
      </div>

      {/* Info Section */}
      <div className="rounded-lg border border-stone-200 bg-stone-50 p-4 dark:border-stone-700 dark:bg-stone-800">
        <h4 className="text-sm font-semibold text-stone-900 dark:text-white">What are API Keys?</h4>
        <ul className="mt-2 space-y-2 text-xs text-stone-600 dark:text-stone-400">
          <li>• <strong>GitHub:</strong> Connect your GitHub account for code context and automation</li>
          <li>• <strong>OpenAI:</strong> Use OpenAI's models for enhanced responses</li>
          <li>• <strong>Claude:</strong> Use Anthropic's Claude model for analysis</li>
          <li>• <strong>Custom:</strong> Connect to any other API provider you use</li>
        </ul>
        <p className="mt-3 text-xs font-medium text-orange-600 dark:text-orange-400">
          ⚠️ Your API keys are encrypted and never shared. You're responsible for keeping them secure.
        </p>
      </div>
    </div>
  )
}
