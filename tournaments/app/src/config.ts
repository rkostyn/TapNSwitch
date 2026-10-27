declare global {
  interface Window {
    __env__?: {
      API_URL?: string
    }
  }
}

export const config = {
  apiUrl: (window.__env__?.API_URL?.startsWith('$') ? null : window.__env__?.API_URL)
    ?? (import.meta.env.VITE_API_URL || null)
    ?? '',
}

// Sentinel opponent for a solo (ghost) match — must match GHOST_PLAYER_ID on the
// API. The ghost scores 0 every throw; displayed to users as "Ghost".
export const GHOST_PLAYER_ID = '__ghost__'
export const GHOST_DISPLAY_NAME = 'Ghost'
