import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types/user'

interface AuthState {
  user:            User | null
  // Derived: true iff user !== null. Using a getter via computed keeps it in sync.
  isAuthenticated: boolean
  login:  (user: User) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user:            null,
      isAuthenticated: false,
      login:  (user) => set({ user, isAuthenticated: true }),
      logout: () => set({ user: null, isAuthenticated: false }),
    }),
    {
      name: 'godspeed-auth',
      // Re-derive isAuthenticated from persisted user on rehydration
      onRehydrateStorage: () => (state) => {
        if (state) {
          state.isAuthenticated = state.user !== null
        }
      },
    },
  ),
)
