import type { ApiEvent, ApiMatch } from './api'

/** Emitted up from EventDetail when a coach has locked a match to score it. */
export interface SelectMatchPayload {
  match: ApiMatch
  event: ApiEvent | null
  /** Lane label for the match ("Red · Lane 1"), or '' when it has no lane. */
  arenaLabel: string
}

/** The event match currently on the scoreboard; null for a casual match. */
export interface MatchContext {
  matchId: string
  eventId: string | null
  player1Id: string
  player2Id: string
  eventName: string
  arenaIds: string[]
  arenaLabel: string
  isFinished: boolean
}
