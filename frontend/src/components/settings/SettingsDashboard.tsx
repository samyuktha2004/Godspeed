import { useState } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { Tabs, TabPanel } from '@/components/common/Tabs'
import { SettingsProfile } from './SettingsProfile'
import { SettingsPreferences } from './SettingsPreferences'
import { SettingsApiKeys } from './SettingsApiKeys'
import { SettingsPrivacy } from './SettingsPrivacy'

type SettingsTab = 'profile' | 'preferences' | 'api-keys' | 'privacy'

const TABS = [
  { id: 'profile'     as const, label: 'Profile'          },
  { id: 'preferences' as const, label: 'Preferences'      },
  { id: 'api-keys'    as const, label: 'API Keys'          },
  { id: 'privacy'     as const, label: 'Privacy & Data'   },
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

      <Tabs tabs={TABS} active={tab} onChange={setTab} className="mb-6" />

      <div className="rounded-lg border border-surface-subtle bg-white dark:bg-stone-900">
        <TabPanel id="profile"     active={tab}><SettingsProfile /></TabPanel>
        <TabPanel id="preferences" active={tab}><SettingsPreferences /></TabPanel>
        <TabPanel id="api-keys"    active={tab}><SettingsApiKeys /></TabPanel>
        <TabPanel id="privacy"     active={tab}><SettingsPrivacy /></TabPanel>
      </div>
    </div>
  )
}
