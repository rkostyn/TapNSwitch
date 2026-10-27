export function readDisplayRoute(): { isDisplay: boolean; arenaId: string | null } {
  const raw = location.hash.startsWith('#/display')
    ? location.hash.slice(1)
    : location.pathname
  const match = raw.match(/^\/display(?:\/([a-z0-9-]+))?\/?$/)
  if (!match) return { isDisplay: false, arenaId: null }
  return { isDisplay: true, arenaId: match[1] ?? null }
}

export function displayUrl(arenaId?: string | null): string {
  return arenaId ? `/display/${arenaId}` : '/display'
}
