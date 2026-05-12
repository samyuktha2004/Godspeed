import { useUIStore } from '@/stores/uiStore'

export function SettingsPreferences() {
  const { isDarkMode, toggleDarkMode } = useUIStore()

  return (
    <div className="space-y-6 p-6">
      {/* Appearance */}
      <div>
        <h3 className="mb-4 text-sm font-semibold">Appearance</h3>
        <div className="flex items-center justify-between rounded-lg border border-stone-200 bg-stone-50 p-4 dark:border-stone-700 dark:bg-stone-900">
          <div>
            <p className="font-medium text-stone-900 dark:text-white">Dark Mode</p>
            <p className="text-xs text-stone-600 dark:text-stone-400">Use dark theme for reduced eye strain</p>
          </div>
          <button
            onClick={toggleDarkMode}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              isDarkMode
                ? 'bg-brand'
                : 'bg-stone-300'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                isDarkMode ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
      </div>

      {/* Notifications */}
      <div className="border-t border-stone-200 pt-6 dark:border-stone-700">
        <h3 className="mb-4 text-sm font-semibold">Notifications</h3>
        <div className="space-y-3">
          {[
            {
              id: 'email_on_query',
              label: 'Email on Query Complete',
              description: 'Get notified when your queries finish processing',
            },
            {
              id: 'email_on_mention',
              label: 'Email on Team Mention',
              description: 'Get notified when a team member mentions you',
            },
            {
              id: 'daily_digest',
              label: 'Daily Digest',
              description: 'Receive a daily summary of team activity',
            },
          ].map((option) => (
            <label key={option.id} className="flex cursor-pointer items-start gap-3">
              <input
                type="checkbox"
                defaultChecked
                className="mt-1 h-4 w-4 rounded border-stone-300 text-brand focus:ring-brand"
              />
              <div>
                <p className="font-medium text-stone-900 dark:text-white">{option.label}</p>
                <p className="text-xs text-stone-600 dark:text-stone-400">{option.description}</p>
              </div>
            </label>
          ))}
        </div>
      </div>

      {/* Query Settings */}
      <div className="border-t border-stone-200 pt-6 dark:border-stone-700">
        <h3 className="mb-4 text-sm font-semibold">Query Settings</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
              Results per page
            </label>
            <select
              defaultValue="10"
              className="mt-2 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-stone-900 shadow-sm focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
            >
              <option value="5">5 results</option>
              <option value="10">10 results</option>
              <option value="20">20 results</option>
              <option value="50">50 results</option>
            </select>
          </div>

          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              defaultChecked
              className="mt-1 h-4 w-4 rounded border-stone-300 text-brand focus:ring-brand"
            />
            <div>
              <p className="font-medium text-stone-900 dark:text-white">Show related documents</p>
              <p className="text-xs text-stone-600 dark:text-stone-400">
                Display related documents in query results
              </p>
            </div>
          </label>

          <label className="flex items-start gap-3">
            <input
              type="checkbox"
              defaultChecked
              className="mt-1 h-4 w-4 rounded border-stone-300 text-brand focus:ring-brand"
            />
            <div>
              <p className="font-medium text-stone-900 dark:text-white">Show knowledge graph</p>
              <p className="text-xs text-stone-600 dark:text-stone-400">
                Display knowledge graph visualization with results
              </p>
            </div>
          </label>
        </div>
      </div>

      {/* Save Button */}
      <div className="border-t border-stone-200 pt-6 dark:border-stone-700">
        <button className="rounded bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark">
          Save Preferences
        </button>
      </div>
    </div>
  )
}
