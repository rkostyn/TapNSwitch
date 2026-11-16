// Pure scoring rules for one match: round and match totals, best-of clinching,
// turn order, clutch availability, the sudden-death tie breaker, and rebuilding
// a match from the throws saved on the server. No Vue, no network.
//
// Player numbers (1/2) are fixed for the match; which side of the screen a
// player is on is a view concern (see `sidesSwapped`).

import type { ApiThrow } from '../api'
import type { PlayerSide, RoundScores, ScoreEntry, Slot } from './types'

export type { PlayerSide, RoundScores, ScoreEntry, ScorePayload, Slot } from './types'

/** Throws per player per regular round. */
export const THROWS = 5
/** A bullseye: both sides sticking one in the tie breaker unlocks clutch. */
export const BULL = 5
/** Consecutive both-missed clutch attempts before the tie breaker drops back to bulls. */
export const MISSED_CLUTCH_LIMIT = 3

export function emptyRound(): Slot[] {
  return Array<Slot>(THROWS).fill(null)
}

export function roundTotal(slots: Slot[]): number {
  return slots.reduce((sum, slot) => sum + (slot ? slot.value : 0), 0)
}

export function throwCount(slots: Slot[]): number {
  return slots.filter(slot => slot !== null).length
}

export function isRoundComplete(scores1: Slot[], scores2: Slot[]): boolean {
  return scores1.every(s => s !== null) && scores2.every(s => s !== null)
}

export type Outcome = 'p1' | 'p2' | 'tie'

export function outcome(p1: number, p2: number): Outcome {
  return p1 > p2 ? 'p1' : p2 > p1 ? 'p2' : 'tie'
}

export interface RoundWins {
  p1: number
  p2: number
}

/** Rounds taken by each player. A level round counts for neither. */
export function countRoundWins(rounds: RoundScores[]): RoundWins {
  let p1 = 0, p2 = 0
  for (const r of rounds) {
    const result = outcome(roundTotal(r.scores1), roundTotal(r.scores2))
    if (result === 'p1') p1++
    else if (result === 'p2') p2++
  }
  return { p1, p2 }
}

/**
 * The live round's scores counted alongside the completed rounds, once the
 * live round is complete.
 */
export function roundsSoFar(completed: RoundScores[], live: RoundScores): RoundScores[] {
  const rounds = [...completed]
  if (isRoundComplete(live.scores1, live.scores2)) rounds.push({ scores1: live.scores1, scores2: live.scores2 })
  return rounds
}

/**
 * Every configured round is played: the game ends when the live round is
 * complete and it was the last round. A 2-0 lead still goes to round 3.
 */
export function isGameOver(liveRoundComplete: boolean, currentRound: number, totalRounds: number): boolean {
  return liveRoundComplete && currentRound === totalRounds
}

export interface RoundRow {
  round: number
  t1: number | null
  t2: number | null
  status: Outcome | 'in-progress' | 'pending'
}

/** One row per scheduled round for the results table. */
export function roundRows(completed: RoundScores[], live: RoundScores, currentRound: number, totalRounds: number): RoundRow[] {
  return Array.from({ length: totalRounds }, (_, i) => {
    const round = i + 1
    const past = completed[i]
    if (round < currentRound && past) {
      const t1 = roundTotal(past.scores1), t2 = roundTotal(past.scores2)
      return { round, t1, t2, status: outcome(t1, t2) }
    } else if (round === currentRound) {
      const t1 = roundTotal(live.scores1), t2 = roundTotal(live.scores2)
      const done = isRoundComplete(live.scores1, live.scores2)
      return { round, t1, t2, status: done ? outcome(t1, t2) : 'in-progress' }
    }
    return { round, t1: null, t2: null, status: 'pending' }
  })
}

/** Sides swap every round; the tie breaker keeps player 1 on the left throughout. */
export function sidesSwapped(round: number, inTiebreak: boolean): boolean {
  return inTiebreak ? false : (round - 1) % 2 === 1
}

/**
 * Put a score into a slot (mutates `slots`): over `selectedIndex` when a
 * placed score is being replaced, otherwise into the first empty slot.
 * Returns where it went and what it replaced, or null when the round is full.
 */
export function placeScore(slots: Slot[], entry: ScoreEntry, selectedIndex: number | null): { index: number; previous: Slot } | null {
  if (selectedIndex !== null) {
    const previous = slots[selectedIndex] ?? null
    slots[selectedIndex] = entry
    return { index: selectedIndex, previous }
  }
  const index = slots.indexOf(null)
  if (index === -1) return null
  slots[index] = entry
  return { index, previous: null }
}

// --- Tie breaker -------------------------------------------------------------
// Equal rounds taken is a draw; sudden death settles it. One throw per side at
// bulls; both sticking a bull goes up to clutch; three clutch attempts in a row
// with neither hitting drops back down to bulls.

export interface Tiebreak {
  phase: 'bull' | 'clutch'
  /** One entry per attempt; the last one is the attempt being thrown. */
  s1: Slot[]
  s2: Slot[]
  missedClutchRounds: number
  winner: PlayerSide | null
}

export function newTiebreak(): Tiebreak {
  return { phase: 'bull', s1: [null], s2: [null], missedClutchRounds: 0, winner: null }
}

export function isTiebreakActive(tb: Tiebreak | null): tb is Tiebreak {
  return !!tb && !tb.winner
}

/** Whether a side has already thrown in the current attempt. */
export function tiebreakThrown(tb: Tiebreak | null, player: PlayerSide): boolean {
  if (!tb) return false
  const arr = player === 1 ? tb.s1 : tb.s2
  return arr[arr.length - 1] !== null
}

/**
 * Each attempt is its own one-slot round on the server, sequenced after the
 * regular rounds.
 */
export function tiebreakSequence(totalRounds: number, tb: Tiebreak | null): number {
  return totalRounds + (tb?.s1.length ?? 0)
}

/**
 * Record a tie-break throw into the current attempt (mutates `tb`). Returns
 * false when it was not accepted: the tie breaker is over, or that side has
 * already thrown this attempt.
 */
export function recordTiebreakThrow(tb: Tiebreak, player: PlayerSide, entry: ScoreEntry): boolean {
  if (tb.winner) return false
  const arr = player === 1 ? tb.s1 : tb.s2
  const idx = arr.length - 1
  if (arr[idx] !== null) return false
  arr[idx] = entry
  return true
}

/**
 * Settle the current attempt once both sides have thrown (mutates `tb`).
 * 'pending' — a side has yet to throw; 'decided' — `tb.winner` is set;
 * 'next' — still level, a fresh attempt has been opened.
 */
export function resolveTiebreakAttempt(tb: Tiebreak): 'pending' | 'decided' | 'next' {
  const idx = tb.s1.length - 1
  const e1 = tb.s1[idx], e2 = tb.s2[idx]
  if (!e1 || !e2) return 'pending'
  const v1 = e1.value, v2 = e2.value
  if (v1 !== v2) {
    tb.winner = v1 > v2 ? 1 : 2
    return 'decided'
  }
  if (tb.phase === 'bull') {
    // Both stuck their bulls — they may go up for clutch
    if (v1 === BULL) tb.phase = 'clutch'
  } else if (v1 > 0) {
    // Both landed a clutch — stay up for clutch
    tb.missedClutchRounds = 0
  } else {
    tb.missedClutchRounds++
    if (tb.missedClutchRounds >= MISSED_CLUTCH_LIMIT) {
      tb.phase = 'bull'
      tb.missedClutchRounds = 0
    }
  }
  // Still tied — open a fresh slot for the next attempt
  tb.s1.push(null)
  tb.s2.push(null)
  return 'next'
}

// --- Scoring pads --------------------------------------------------------------

export interface PadState {
  /** The ghost's side in a solo match, or null. */
  ghostSide: PlayerSide | null
  /** A placed score selected for replacement. */
  selected: { player: PlayerSide; index: number } | null
  /** An earlier round is open for review/editing. */
  reviewing: boolean
  tiebreak: Tiebreak | null
  /** Throws so far in the live round. */
  throws1: number
  throws2: number
}

/**
 * Alternating-throw rules only gate the live round; past rounds edit freely.
 * During a tie breaker a side locks once its throw for the current attempt is in.
 */
export function isPadDisabled(player: PlayerSide, s: PadState): boolean {
  if (player === s.ghostSide) return true // the ghost never throws by hand
  if (s.selected?.player === player) return false // editing a placed score
  if (s.reviewing) return false
  if (isTiebreakActive(s.tiebreak)) return tiebreakThrown(s.tiebreak, player)
  return player === 1 ? s.throws1 > s.throws2 : s.throws2 > s.throws1
}

/** Clutch can be called on a side's final throw of a round, or in the tie breaker's clutch phase. */
export function isClutchAvailable(player: PlayerSide, s: PadState): boolean {
  if (s.reviewing) return true
  if (isTiebreakActive(s.tiebreak)) return s.tiebreak.phase === 'clutch'
  // Replacing the last and final throw? Clutch is still on the table.
  if (s.selected?.player === player && s.selected.index === THROWS - 1) return true
  return (player === 1 ? s.throws1 : s.throws2) === THROWS - 1
}

// --- Restoring from the server -------------------------------------------------

export interface RestoredMatch {
  completed: RoundScores[]
  currentRound: number
  scores1: Slot[]
  scores2: Slot[]
}

/**
 * Rebuild a match's regular rounds from its saved rounds and throws. Throws
 * fill each player's slots in timestamp order. Leading complete rounds become
 * completed rounds; the first incomplete (or missing) round — or the last
 * scheduled round, even when complete — becomes the live round. Tie-break
 * rounds (sequence past `totalRounds`) are not restored.
 */
export function restoreMatch(
  roundIdBySeq: Record<number, string>,
  throws: ApiThrow[],
  player1Id: string,
  player2Id: string,
  totalRounds: number,
): RestoredMatch {
  const bySeq: Record<number, { arr1: Slot[]; arr2: Slot[] }> = {}
  for (const [seq, roundId] of Object.entries(roundIdBySeq)) {
    const arr1 = emptyRound()
    const arr2 = emptyRound()
    const roundThrows = throws
      .filter(t => t.round_id === roundId)
      .sort((a, b) => (a.timestamp < b.timestamp ? -1 : 1))
    for (const t of roundThrows) {
      const arr = t.player_id === player1Id ? arr1 : t.player_id === player2Id ? arr2 : null
      if (!arr) continue
      const idx = arr.indexOf(null)
      if (idx !== -1) arr[idx] = { value: t.points, drop: !!t.is_drop, throwId: t.throw_id }
    }
    bySeq[Number(seq)] = { arr1, arr2 }
  }

  const completed: RoundScores[] = []
  let currentRound = 1
  let live: { arr1: Slot[]; arr2: Slot[] } | null = null
  for (let seq = 1; seq <= totalRounds; seq++) {
    const entry = bySeq[seq]
    if (entry && !entry.arr1.includes(null) && !entry.arr2.includes(null) && seq < totalRounds) {
      completed.push({ scores1: entry.arr1, scores2: entry.arr2 })
      continue
    }
    currentRound = seq
    live = entry ?? null
    break
  }
  return {
    completed,
    currentRound,
    scores1: live ? live.arr1 : emptyRound(),
    scores2: live ? live.arr2 : emptyRound(),
  }
}
