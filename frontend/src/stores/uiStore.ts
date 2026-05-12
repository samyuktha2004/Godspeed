import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface Toast {
  id:      string
  message: string
  type:    'info' | 'success' | 'warning' | 'error'
}

interface UIState {
  theme:          'light' | 'dark'
  sidebarOpen:    boolean
  graphCollapsed: boolean
  toasts:         Toast[]
  toggleTheme:         () => void
  toggleSidebar:       () => void
  toggleGraphCollapsed: () => void
  addToast:    (toast: Omit<Toast, 'id'>) => void
  removeToast: (id: string) => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      theme:          'light',
      sidebarOpen:    true,
      graphCollapsed: false,
      toasts:         [],

      toggleTheme: () =>
        set((s) => ({ theme: s.theme === 'light' ? 'dark' : 'light' })),

      toggleSidebar: () =>
        set((s) => ({ sidebarOpen: !s.sidebarOpen })),

      toggleGraphCollapsed: () =>
        set((s) => ({ graphCollapsed: !s.graphCollapsed })),

      addToast: (toast) =>
        set((s) => ({
          toasts: [...s.toasts, { ...toast, id: crypto.randomUUID() }],
        })),

      removeToast: (id) =>
        set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
    }),
    { name: 'godspeed-ui', partialize: (s) => ({ theme: s.theme, graphCollapsed: s.graphCollapsed }) },
  ),
)
