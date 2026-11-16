// The venue floor layout (arenas, their colors and lanes), loaded once from
// `GET /venue` at start-up. Until it loads, or if it fails, the label helpers
// fall back to the raw ids.

import { reactive, readonly } from 'vue'
import { getVenue, type VenueArena } from './api'

export type { VenueArena } from './api'

const state = reactive<{ name: string | null; arenas: VenueArena[] }>({
  name: null,
  arenas: [],
})

/** The loaded layout; `arenas` is empty until `loadVenue` succeeds. */
export const venue = readonly(state)

let loading: Promise<void> | null = null

/** Load the layout. Never rejects; a failed load can be retried by calling again. */
export function loadVenue(): Promise<void> {
  loading ??= getVenue()
    .then(layout => {
      state.name = layout.venue
      state.arenas = layout.arenas
    })
    .catch(e => {
      console.error('Failed to load the venue layout; arena and lane labels will show raw ids', e)
      loading = null
    })
  return loading
}

export function arenaById(arenaId: string): VenueArena | undefined {
  return state.arenas.find(arena => arena.arena_id === arenaId)
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
  const lane = arena.lanes.find(l => l.lane_id === laneId)
  if (lane) return `${arena.name} · ${lane.label}`
  const num = laneId.slice(arenaId.length + 1)
  return num ? `${arena.name} · Lane ${num}` : arena.name
}
