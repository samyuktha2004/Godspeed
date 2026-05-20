// eslint-disable-next-line @typescript-eslint/no-explicit-any
const _env = (import.meta as any).env

export const env = {
  // Empty string → relative URLs → works when frontend is served from FastAPI via ngrok
  apiBaseUrl: _env.VITE_API_BASE_URL || '',

  // Derived at runtime from page host so WebSocket works on any ngrok URL automatically
  get wsBaseUrl(): string {
    if (_env.VITE_WS_BASE_URL) return _env.VITE_WS_BASE_URL
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${window.location.host}`
  },
}
