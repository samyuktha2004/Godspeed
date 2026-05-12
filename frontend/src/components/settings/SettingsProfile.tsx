import { useState } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { useForm } from 'react-hook-form'

interface ProfileFormData {
  name: string
  email: string
  current_password?: string
  new_password?: string
  confirm_password?: string
}

export function SettingsProfile() {
  const { user } = useAuth()
  const { register, handleSubmit, reset, formState: { errors }, watch } = useForm<ProfileFormData>({
    defaultValues: {
      name: user?.name || '',
      email: user?.email || '',
    },
  })
  const [showPasswordForm, setShowPasswordForm] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const newPassword = watch('new_password')

  const onSubmitProfile = async (data: ProfileFormData) => {
    setIsLoading(true)
    setMessage(null)
    try {
      // TODO: Call PATCH /api/auth/profile endpoint
      console.log('Update profile:', data)
      setMessage({ type: 'success', text: 'Profile updated successfully' })
      reset(data)
    } catch (err) {
      setMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to update profile',
      })
    } finally {
      setIsLoading(false)
    }
  }

  const onSubmitPassword = async (data: ProfileFormData) => {
    if (data.new_password !== data.confirm_password) {
      setMessage({ type: 'error', text: 'Passwords do not match' })
      return
    }

    setIsLoading(true)
    setMessage(null)
    try {
      // TODO: Call POST /api/auth/change-password endpoint
      console.log('Change password:', {
        current_password: data.current_password,
        new_password: data.new_password,
      })
      setMessage({ type: 'success', text: 'Password changed successfully' })
      setShowPasswordForm(false)
      reset({ ...watch(), current_password: '', new_password: '', confirm_password: '' })
    } catch (err) {
      setMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to change password',
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmitProfile)} className="space-y-6 p-6">
      {/* Account Info */}
      <div>
        <h3 className="mb-4 text-sm font-semibold">Account Information</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
              Full Name
            </label>
            <input
              type="text"
              {...register('name', { required: 'Name is required' })}
              className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-stone-900 shadow-sm placeholder-stone-400 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
            />
            {errors.name && <p className="mt-1 text-xs text-red-500">{errors.name.message}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
              Email
            </label>
            <input
              type="email"
              {...register('email')}
              disabled
              className="mt-1 block w-full rounded border border-stone-300 bg-stone-100 px-3 py-2 text-stone-500 shadow-sm dark:border-stone-600 dark:bg-stone-900 dark:text-stone-400"
            />
            <p className="mt-1 text-xs text-stone-500">Email cannot be changed</p>
          </div>
        </div>
      </div>

      {/* Message */}
      {message && (
        <div
          className={`rounded-md p-3 text-sm ${
            message.type === 'success'
              ? 'border border-green-200 bg-green-50 text-green-800 dark:border-green-900 dark:bg-green-950 dark:text-green-200'
              : 'border border-red-200 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200'
          }`}
        >
          {message.text}
        </div>
      )}

      {/* Save Button */}
      <div className="flex gap-2 border-t border-stone-200 pt-6 dark:border-stone-700">
        <button
          type="submit"
          disabled={isLoading}
          className="rounded bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
        >
          {isLoading ? 'Saving...' : 'Save Changes'}
        </button>
      </div>

      {/* Password Section */}
      <div className="border-t border-stone-200 pt-6 dark:border-stone-700">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold">Password</h3>
            <p className="mt-1 text-xs text-stone-500">Change your password to keep your account secure</p>
          </div>
          <button
            type="button"
            onClick={() => setShowPasswordForm(!showPasswordForm)}
            className="text-sm font-medium text-brand hover:underline"
          >
            {showPasswordForm ? 'Cancel' : 'Change Password'}
          </button>
        </div>

        {showPasswordForm && (
          <form onSubmit={handleSubmit(onSubmitPassword)} className="mt-4 space-y-4">
            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
                Current Password
              </label>
              <input
                type="password"
                {...register('current_password', { required: 'Current password is required' })}
                className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-stone-900 shadow-sm placeholder-stone-400 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
              />
              {errors.current_password && (
                <p className="mt-1 text-xs text-red-500">{errors.current_password.message}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
                New Password
              </label>
              <input
                type="password"
                {...register('new_password', {
                  required: 'New password is required',
                  minLength: { value: 8, message: 'Password must be at least 8 characters' },
                })}
                className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-stone-900 shadow-sm placeholder-stone-400 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
              />
              {errors.new_password && (
                <p className="mt-1 text-xs text-red-500">{errors.new_password.message}</p>
              )}
            </div>

            <div>
              <label className="block text-sm font-medium text-stone-700 dark:text-stone-300">
                Confirm New Password
              </label>
              <input
                type="password"
                {...register('confirm_password', {
                  required: 'Please confirm your password',
                  validate: (value) => value === newPassword || 'Passwords do not match',
                })}
                className="mt-1 block w-full rounded border border-stone-300 bg-white px-3 py-2 text-stone-900 shadow-sm placeholder-stone-400 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand dark:border-stone-600 dark:bg-stone-800 dark:text-white"
              />
              {errors.confirm_password && (
                <p className="mt-1 text-xs text-red-500">{errors.confirm_password.message}</p>
              )}
            </div>

            <div className="flex gap-2">
              <button
                type="submit"
                disabled={isLoading}
                className="rounded bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-50"
              >
                {isLoading ? 'Updating...' : 'Update Password'}
              </button>
              <button
                type="button"
                onClick={() => setShowPasswordForm(false)}
                className="rounded border border-stone-300 px-4 py-2 text-sm font-medium text-stone-700 hover:bg-stone-50 dark:border-stone-600 dark:text-stone-300 dark:hover:bg-stone-800"
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>
    </form>
  )
}
