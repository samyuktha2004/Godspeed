import { env } from '@/config/env'
import { useAuthStore } from '@/stores/authStore'
import { useUIStore } from '@/stores/uiStore'

// ─── Typed API errors ────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly requestId?: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

// ─── Token refresh ───────────────────────────────────────────────────────────

async function refreshToken(): Promise<boolean> {
  try {
    const res = await fetch(`${env.apiBaseUrl}/api/auth/refresh`, {
      method:      'POST',
      credentials: 'include',
    })
    return res.ok
  } catch {
    return false
  }
}

// ─── Error handling ──────────────────────────────────────────────────────────

/** Parse a non-OK response and show the appropriate toast, then throw ApiError. */
async function handleErrorResponse(res: Response): Promise<never> {
  const requestId = res.headers.get('X-Request-ID') ?? undefined
  const addToast  = useUIStore.getState().addToast

  let message: string
  try {
    const json = await res.json()
    message = json.detail ?? json.message ?? res.statusText
  } catch {
    message = res.statusText || `HTTP ${res.status}`
  }

  switch (res.status) {
    case 429: {
      const retryAfter = res.headers.get('Retry-After')
      const suffix = retryAfter ? ` — retry in ${retryAfter}s` : ''
      addToast({ type: 'warning', message: `Rate limited${suffix}` })
      break
    }
    case 403:
      // RBAC — components handle this via RBACRestrictedBanner; no toast needed
      break
    case 502:
    case 503:
    case 504:
      addToast({ type: 'error', message: 'Backend unavailable — try again shortly' })
      break
    case 500:
      addToast({
        type:    'error',
        message: requestId
          ? `Server error [${requestId}] — contact support if this persists`
          : 'Server error — try again',
      })
      break
    default:
      if (res.status >= 400) {
        addToast({ type: 'error', message })
      }
  }

  throw new ApiError(res.status, message, requestId)
}

// ─── Base fetch ──────────────────────────────────────────────────────────────

export async function apiFetch(
  path: string,
  init: RequestInit = {},
): Promise<Response> {
  const doFetch = () =>
    fetch(`${env.apiBaseUrl}${path}`, {
      ...init,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        ...init.headers,
      },
    })

  let res: Response
  try {
    res = await doFetch()
  } catch {
    // Network-level failure (DNS, no connection)
    useUIStore.getState().addToast({ type: 'error', message: 'No connection to server' })
    throw new ApiError(0, 'Network error')
  }

  if (res.status === 401) {
    const refreshed = await refreshToken()
    if (!refreshed) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
      throw new ApiError(401, 'Session expired')
    }
    try {
      res = await doFetch()
    } catch {
      throw new ApiError(0, 'Network error after token refresh')
    }
  }

  if (!res.ok) {
    await handleErrorResponse(res)
  }

  return res
}

// ─── SSE streaming fetch ─────────────────────────────────────────────────────

/** Returns raw Response for streaming — does NOT parse body. */
export async function ssePost(
  path: string,
  body: unknown,
  signal: AbortSignal,
): Promise<Response> {
  const doFetch = () =>
    fetch(`${env.apiBaseUrl}${path}`, {
      method:      'POST',
      credentials: 'include',
      signal,
      headers: {
        'Content-Type':  'application/json',
        'Accept':        'text/event-stream',
        'Cache-Control': 'no-cache',
      },
      body: JSON.stringify(body),
    })

  let res: Response
  try {
    res = await doFetch()
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err
    useUIStore.getState().addToast({ type: 'error', message: 'No connection to server' })
    throw new ApiError(0, 'Network error')
  }

  if (res.status === 401) {
    const refreshed = await refreshToken()
    if (!refreshed) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
      throw new ApiError(401, 'Session expired')
    }
    try {
      res = await doFetch()
    } catch (err) {
      if ((err as Error).name === 'AbortError') throw err
      throw new ApiError(0, 'Network error after token refresh')
    }
  }

  if (!res.ok) {
    const requestId = res.headers.get('X-Request-ID') ?? undefined
    const text = await res.text().catch(() => res.statusText)
    throw new ApiError(res.status, `${res.status}: ${text}`, requestId)
  }

  return res
}
