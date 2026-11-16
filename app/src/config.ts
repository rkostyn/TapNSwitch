declare global {
  interface Window {
    __env__?: {
      API_URL?: string
    }
  }
}

// Runtime values come from public/env-config.js, which docker/entrypoint.sh fills
// in with envsubst. Locally (vite dev) it is served unsubstituted, so a value that
// still starts with '$' means "not set".
export const config = {
  apiUrl: (window.__env__?.API_URL?.startsWith('$') ? null : window.__env__?.API_URL)
    ?? (import.meta.env.VITE_API_URL || null)
    ?? '',
}

export type PairingStyle = 'round_robin' | 'swiss'

export { GHOST_PLAYER_ID, GHOST_DISPLAY_NAME } from './ghost'
