import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types/user'

interface AuthState {
  user:            User | null
  isAuthenticated: boolean
  setupComplete:   boolean
  login:           (user: User) => void
  logout:          () => void
  markSetupComplete: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user:            null,
      isAuthenticated: false,
      setupComplete:   false,

      login: (user) => set({ user, isAuthenticated: true }),

      logout: () => set({ user: null, isAuthenticated: false, setupComplete: false }),

      markSetupComplete: () => set({ setupComplete: true }),
    }),
    {
      name: 'godspeed-auth',
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.isAuthenticated = state.user !== null
        }
      },
    },
  ),
)
