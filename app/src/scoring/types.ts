/** Which player a score belongs to (player 1 / player 2, not left / right). */
export type PlayerSide = 1 | 2

/** One recorded throw in a score slot. */
export interface ScoreEntry {
  value: number
  clutch?: boolean
  drop?: boolean
  /** Server id once the throw has been saved (event matches only). */
  throwId?: string
}

/** A score slot: a recorded throw, or null while it has not been thrown. */
export type Slot = ScoreEntry | null

export interface RoundScores {
  scores1: Slot[]
  scores2: Slot[]
}

/** What a scoring pad emits when a button is tapped. */
export interface ScorePayload {
  points: number
  clutch: boolean
  drop?: boolean
}
