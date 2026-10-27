export interface VenueArena {
  arena_id: string
  name: string
  color: string
  text_color: string
}

export const ARENAS: VenueArena[] = [
  { arena_id: 'red', name: 'Red', color: '#dc2626', text_color: '#ffffff' },
  { arena_id: 'green', name: 'Green', color: '#16a34a', text_color: '#ffffff' },
  { arena_id: 'blue', name: 'Blue', color: '#2563eb', text_color: '#ffffff' },
  { arena_id: 'yellow', name: 'Yellow', color: '#eab308', text_color: '#111827' },
  { arena_id: 'white', name: 'White', color: '#e5e7eb', text_color: '#111827' },
  { arena_id: 'black', name: 'Black', color: '#171717', text_color: '#ffffff' },
]

export function arenaById(arenaId: string): VenueArena | undefined {
  return ARENAS.find(arena => arena.arena_id === arenaId)
}

export function arenaLabel(arenaIds: string[] | null | undefined): string {
  if (!arenaIds?.length) return ''
  return arenaIds.map(id => arenaById(id)?.name ?? id).join(' / ')
}

export function laneLabel(laneId: string | null | undefined): string {
  if (!laneId) return ''
  const arenaId = laneId.includes('-') ? laneId.slice(0, laneId.lastIndexOf('-')) : laneId
  const arena = arenaById(arenaId)
  if (!arena) return laneId
  const num = laneId.slice(arenaId.length + 1)
  return num ? `${arena.name} · Lane ${num}` : arena.name
}
