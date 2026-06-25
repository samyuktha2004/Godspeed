import { useState } from 'react'
import { apiFetch } from '@/lib/http'
import { useUIStore } from '@/stores/uiStore'

export function SettingsPrivacy() {
  const addToast = useUIStore((s) => s.addToast)
  const [exportRequested, setExportRequested] = useState(false)
  const [deleteRequested, setDeleteRequested] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [isLoading, setIsLoading] = useState<'export' | 'delete' | null>(null)

  const handleExport = async () => {
    setIsLoading('export')
    try {
      await apiFetch('/api/auth/me/data-export', { method: 'POST' })
      setExportRequested(true)
      addToast({ type: 'success', message: 'Data export requested — you will receive an email when it is ready.' })
    } catch {
      addToast({ type: 'error', message: 'Could not submit export request. Please try again.' })
    } finally {
      setIsLoading(null)
    }
  }

  const handleDelete = async () => {
    setIsLoading('delete')
    try {
      await apiFetch('/api/auth/me/delete-request', { method: 'POST' })
      setDeleteRequested(true)
      addToast({ type: 'success', message: 'Account deletion requested. Your workspace admin will be notified.' })
    } catch {
      addToast({ type: 'error', message: 'Could not submit deletion request. Please try again.' })
    } finally {
      setIsLoading(null)
      setConfirmDelete(false)
    }
  }

  return (
    <div className="space-y-8 p-6">

      {/* Overview */}
      <div>
        <h3 className="mb-1 text-sm font-semibold">Data & Privacy</h3>
        <p className="text-xs text-stone-500 leading-relaxed">
          Godspeed processes your personal data in accordance with its{' '}
          <a href="/privacy" target="_blank" rel="noopener noreferrer" className="text-brand hover:underline">Privacy Policy</a>
          {' '}and applicable law, including India's Digital Personal Data Protection Act (DPDPA).
          You have the rights described below at any time.
        </p>
      </div>

      {/* Right to Access / Data Export */}
      <div className="rounded-lg border border-surface-subtle p-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium">Export my data</p>
            <p className="mt-1 text-xs text-stone-500 leading-relaxed">
              Request a copy of the personal data Godspeed holds about you (Right to Access under DPDPA §11).
              You will receive a download link by email within 72 hours.
            </p>
          </div>
          <button
            onClick={handleExport}
            disabled={!!isLoading || exportRequested}
            className="shrink-0 rounded border border-stone-300 px-3 py-1.5 text-xs font-medium text-stone-700 hover:bg-stone-50 disabled:opacity-50 dark:border-stone-600 dark:text-stone-300 dark:hover:bg-stone-800"
          >
            {exportRequested ? 'Requested' : isLoading === 'export' ? 'Submitting…' : 'Request export'}
          </button>
        </div>
      </div>

      {/* Right to Erasure / Account Deletion */}
      <div className="rounded-lg border border-red-200 p-4 dark:border-red-900">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-red-700 dark:text-red-400">Delete my account</p>
            <p className="mt-1 text-xs text-stone-500 leading-relaxed">
              Request permanent erasure of your account and personal data (Right to Erasure under DPDPA §12).
              Your workspace admin will be notified and data will be deleted within 30 days, except where
              retention is required by law or legitimate business need.
            </p>
          </div>
          {!confirmDelete ? (
            <button
              onClick={() => setConfirmDelete(true)}
              disabled={!!isLoading || deleteRequested}
              className="shrink-0 rounded border border-red-300 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50 dark:border-red-800 dark:text-red-400 dark:hover:bg-red-950"
            >
              {deleteRequested ? 'Requested' : 'Request deletion'}
            </button>
          ) : (
            <div className="flex shrink-0 flex-col items-end gap-2">
              <p className="text-xs font-medium text-red-600 dark:text-red-400">Are you sure?</p>
              <div className="flex gap-2">
                <button
                  onClick={() => setConfirmDelete(false)}
                  className="rounded border border-stone-300 px-2 py-1 text-xs text-stone-600 hover:bg-stone-50 dark:border-stone-600 dark:text-stone-300"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDelete}
                  disabled={!!isLoading}
                  className="rounded bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
                >
                  {isLoading === 'delete' ? 'Submitting…' : 'Yes, delete'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Policy links */}
      <div className="border-t border-surface-subtle pt-4">
        <p className="text-xs text-stone-400">
          For questions about how your data is used, contact your Data Protection Officer or review our{' '}
          <a href="/privacy" target="_blank" rel="noopener noreferrer" className="text-brand hover:underline">Privacy Policy</a>
          {' '}and{' '}
          <a href="/terms" target="_blank" rel="noopener noreferrer" className="text-brand hover:underline">Terms of Service</a>.
        </p>
      </div>
    </div>
  )
}
