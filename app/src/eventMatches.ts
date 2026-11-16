// Pure helpers for an event's group-stage match list.

import type { ApiMatch } from './api'
import { GHOST_DISPLAY_NAME, GHOST_PLAYER_ID } from './ghost'

function involvesLate(match: ApiMatch, late: Set<string | null>): boolean {
  return late.has(match.player_1_id) || late.has(match.player_2_id)
}

/**
 * Upcoming matches first, late throwers' matches next, completed at the
 * bottom — so whoever is up next is always at the top. Ties keep schedule order.
 */
export function sortForMatchList(matches: ApiMatch[], latePlayers: string[]): ApiMatch[] {
  const late = new Set<string | null>(latePlayers)
  const rank = (m: ApiMatch) => (m.is_finished ? 2 : involvesLate(m, late) ? 1 : 0)
  return [...matches].sort((a, b) => rank(a) - rank(b) || a.sequence - b.sequence)
}

/** An unfinished match held back because one of its throwers is late. */
export function isDelayedByLate(match: ApiMatch, latePlayers: string[]): boolean {
  return !match.is_finished && involvesLate(match, new Set<string | null>(latePlayers))
}

export function displayPlayer(id: string | null): string {
  if (!id) return 'TBD'
  return id === GHOST_PLAYER_ID ? GHOST_DISPLAY_NAME : id
}

export function matchLabel(match: ApiMatch): string {
  return `${displayPlayer(match.player_1_id)} vs ${displayPlayer(match.player_2_id)}`
}

export function matchStatus(match: ApiMatch): 'finished' | 'locked' | 'open' {
  if (match.is_finished) return 'finished'
  if (match.is_locked) return 'locked'
  return 'open'
}
