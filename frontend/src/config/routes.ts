import {
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
} from '@tanstack/react-router'
import { lazy } from 'react'

import App from '@/App'
import { useAuthStore } from '@/stores/authStore'
import { isAdmin, isOwner } from '@/lib/utils'

const Home          = lazy(() => import('@/pages/Home'))
const QueryPage     = lazy(() => import('@/pages/QueryPage'))
const Analytics     = lazy(() => import('@/pages/AnalyticsPage'))
const Admin         = lazy(() => import('@/pages/AdminPage'))
const Workspace     = lazy(() => import('@/pages/WorkspacePage'))
const Settings      = lazy(() => import('@/pages/SettingsPage'))
const Login         = lazy(() => import('@/pages/LoginPage'))
const Register      = lazy(() => import('@/pages/RegisterPage'))
const Setup         = lazy(() => import('@/pages/SetupPage'))
const OAuthCallback = lazy(() => import('@/pages/OAuthCallbackPage'))
const AcceptInvite  = lazy(() => import('@/pages/AcceptInvitePage'))
const PrivacyPolicy = lazy(() => import('@/pages/PrivacyPolicyPage'))
const Terms         = lazy(() => import('@/pages/TermsPage'))
const NotFound      = lazy(() => import('@/pages/NotFoundPage'))

const requireAuth = () => {
  if (!useAuthStore.getState().isAuthenticated) {
    throw redirect({ to: '/login' })
  }
}

const requireAdmin = () => {
  requireAuth()
  if (!isAdmin(useAuthStore.getState().user)) {
    throw redirect({ to: '/' })
  }
}

const requireOwner = () => {
  requireAuth()
  if (!isOwner(useAuthStore.getState().user)) {
    throw redirect({ to: '/' })
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
    q:     typeof s.q   === 'string' ? s.q   : undefined,
    qid:   typeof s.qid === 'string' ? s.qid : undefined,
    fresh: s.fresh === true || s.fresh === 'true',
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
  beforeLoad:     requireAdmin,
  component:      Admin,
})

export const workspaceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/workspace',
  beforeLoad:     requireAuth,
  component:      Workspace,
  validateSearch: (s: Record<string, unknown>) => ({
    id: typeof s.id === 'string' ? s.id : undefined,
  }),
})

export const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/settings',
  beforeLoad:     requireAuth,
  component:      Settings,
})

export const registerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path:           '/register',
  component:      Register,
})

export const setupRoute = createRoute({
  getParentRoute: () => rootRoute,
  path:           '/setup',
  beforeLoad:     requireOwner,
  component:      Setup,
})

export const acceptInviteRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/accept-invite',
  component: AcceptInvite,
  validateSearch: (s: Record<string, unknown>) => ({
    token: typeof s.token === 'string' ? s.token : '',
  }),
})

export const privacyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path:           '/privacy',
  component:      PrivacyPolicy,
})

export const termsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path:           '/terms',
  component:      Terms,
})

export const notFoundRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '*',
  component:      NotFound,
})

const routeTree = rootRoute.addChildren([
  loginRoute,
  registerRoute,
  setupRoute,
  oauthCallbackRoute,
  acceptInviteRoute,
  homeRoute,
  queryRoute,
  analyticsRoute,
  adminRoute,
  workspaceRoute,
  settingsRoute,
  privacyRoute,
  termsRoute,
  notFoundRoute,
])

export const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register { router: typeof router }
}
