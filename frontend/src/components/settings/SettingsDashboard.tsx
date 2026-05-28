import { useState } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { env } from '@/config/env'
import { SettingsProfile } from './SettingsProfile'
import { SettingsPreferences } from './SettingsPreferences'
import { SettingsApiKeys } from './SettingsApiKeys'

type SettingsTab = 'profile' | 'preferences' | 'api-keys'

const TABS: { id: SettingsTab; label: string }[] = [
  { id: 'profile', label: 'Profile' },
  { id: 'preferences', label: 'Preferences' },
  // API Keys is stub UI — kept behind a feature flag until the backend exists.
  ...(env.enableApiKeysTab ? [{ id: 'api-keys' as SettingsTab, label: 'API Keys' }] : []),
]

export function SettingsDashboard() {
  const [tab, setTab] = useState<SettingsTab>('profile')
  const { user } = useAuth()

  if (!user) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-stone-500">Loading...</p>
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="mb-2 text-3xl font-semibold">Settings</h1>
      <p className="mb-6 text-sm text-stone-500">Manage your account and preferences</p>

      {/* Tab Navigation */}
      <div className="mb-6 flex gap-1 overflow-x-auto border-b border-surface-subtle">
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`whitespace-nowrap px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.id
                ? 'border-b-2 border-brand text-brand'
                : 'text-stone-500 hover:text-stone-700 dark:hover:text-stone-300'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="rounded-lg border border-surface-subtle bg-white dark:bg-stone-900">
        {tab === 'profile' && <SettingsProfile />}
        {tab === 'preferences' && <SettingsPreferences />}
        {tab === 'api-keys' && env.enableApiKeysTab && <SettingsApiKeys />}
      </div>
    </div>
  )
}
