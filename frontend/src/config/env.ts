const get = (key: string): string => {
  const val = import.meta.env[key]
  if (!val) throw new Error(`Missing env var: ${key}`)
  return val
}

export const env = {
  apiBaseUrl: get('VITE_API_BASE_URL'),
  wsBaseUrl:  get('VITE_WS_BASE_URL'),
} as const
