declare global {
  interface Window {
    __env__?: {
      API_URL?: string
    }
  }
}

export const config = {
  apiUrl: (window.__env__?.API_URL?.startsWith('$') ? null : window.__env__?.API_URL)
    ?? import.meta.env.VITE_API_URL
    ?? 'http://localhost:8000',
}
