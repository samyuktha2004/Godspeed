import {
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
} from '@tanstack/react-router'
import { lazy } from 'react'

import App from '@/App'
import { useAuthStore } from '@/stores/authStore'

const Home          = lazy(() => import('@/pages/Home'))
const QueryPage     = lazy(() => import('@/pages/QueryPage'))
const Analytics     = lazy(() => import('@/pages/AnalyticsPage'))
const Admin         = lazy(() => import('@/pages/AdminPage'))
const Workspace     = lazy(() => import('@/pages/WorkspacePage'))
const Settings      = lazy(() => import('@/pages/SettingsPage'))
const Login         = lazy(() => import('@/pages/LoginPage'))
const OAuthCallback = lazy(() => import('@/pages/OAuthCallbackPage'))
const NotFound      = lazy(() => import('@/pages/NotFoundPage'))

const requireAuth = () => {
  if (!useAuthStore.getState().isAuthenticated) {
    throw redirect({ to: '/login' })
  }
}

const rootRoute = createRootRoute({ component: App })

export const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  component: Login,
})

export const oauthCallbackRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/auth/callback',
  component: OAuthCallback,
  validateSearch: (s: Record<string, unknown>) => ({
    oauth: typeof s.oauth === 'string' ? s.oauth : undefined,
    error: typeof s.error === 'string' ? s.error : undefined,
  }),
})

export const homeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/',
  beforeLoad:     requireAuth,
  component:      Home,
})

export const queryRoute = createRoute({
  getParentRoute:     () => rootRoute,
  path:               '/query',
  beforeLoad:         requireAuth,
  component:          QueryPage,
  validateSearch: (s: Record<string, unknown>) => ({
    q: typeof s.q === 'string' ? s.q : undefined,
  }),
})

export const analyticsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/analytics',
  beforeLoad:     requireAuth,
  component:      Analytics,
})

export const adminRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/admin',
  beforeLoad:     requireAuth,
  component:      Admin,
})

export const workspaceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/workspace',
  beforeLoad:     requireAuth,
  component:      Workspace,
})

export const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings',
  beforeLoad:     requireAuth,
  component:      Settings,
})

export const notFoundRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '*',
  component:      NotFound,
})

const routeTree = rootRoute.addChildren([
  loginRoute,
  oauthCallbackRoute,
  homeRoute,
  queryRoute,
  analyticsRoute,
  adminRoute,
  workspaceRoute,
  settingsRoute,
  notFoundRoute,
])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register { router: typeof router }
}
