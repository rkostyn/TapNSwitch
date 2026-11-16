import { describe, expect, it } from 'vitest'
import type { ApiThrow } from '../../api'
import {
  THROWS,
  countRoundWins,
  emptyRound,
  isClutchAvailable,
  isGameOver,
  isPadDisabled,
  isRoundComplete,
  isTiebreakActive,
  newTiebreak,
  outcome,
  placeScore,
  recordTiebreakThrow,
  resolveTiebreakAttempt,
  restoreMatch,
  roundRows,
  roundTotal,
  roundsSoFar,
  sidesSwapped,
  throwCount,
  tiebreakSequence,
  tiebreakThrown,
  type PadState,
  type RoundScores,
  type Slot,
  type Tiebreak,
} from '../rules'

/** Slots from point values; null = not thrown yet. */
const s = (...values: (number | null)[]): Slot[] => values.map(v => (v === null ? null : { value: v }))
const round = (a: (number | null)[], b: (number | null)[]): RoundScores => ({ scores1: s(...a), scores2: s(...b) })
const full = (total1: number, total2: number) =>
  // A complete round with the given totals (one non-zero throw each, rest 0)
  round([total1, 0, 0, 0, 0], [total2, 0, 0, 0, 0])

describe('round totals', () => {
  it('sums thrown slots and ignores empty ones', () => {
    expect(roundTotal(s(5, 3, null, 1, 0))).toBe(9)
    expect(roundTotal(emptyRound())).toBe(0)
  })

  it('counts drops and clutch scores by their value', () => {
    expect(roundTotal([{ value: 0, drop: true }, { value: 7, clutch: true }, null, null, null])).toBe(7)
  })

  it('counts throws', () => {
    expect(throwCount(s(0, null, 3, null, null))).toBe(2)
  })

  it('a round is complete only when both players have all five throws', () => {
    expect(THROWS).toBe(5)
    expect(isRoundComplete(s(1, 1, 1, 1, 1), s(1, 1, 1, 1, 1))).toBe(true)
    expect(isRoundComplete(s(1, 1, 1, 1, 1), s(1, 1, 1, 1, null))).toBe(false)
  })
})

describe('round and match outcome', () => {
  it('a level round counts for neither player', () => {
    expect(outcome(10, 10)).toBe('tie')
    expect(countRoundWins([full(10, 10), full(12, 3), full(3, 12), full(1, 0)])).toEqual({ p1: 2, p2: 1 })
  })

  it('counts the live round only once it is complete', () => {
    const done = [full(5, 0)]
    expect(roundsSoFar(done, round([5, 0, 0, 0, null], [0, 0, 0, 0, 0]))).toHaveLength(1)
    expect(roundsSoFar(done, full(0, 5))).toHaveLength(2)
  })

  it('ends only after the last configured round', () => {
    // Round 3 of 3 complete
    expect(isGameOver(true, 3, 3)).toBe(true)
    // Round 2 of 3 complete: play on, even with a 2-0 lead
    expect(isGameOver(true, 2, 3)).toBe(false)
    // Last round still being thrown
    expect(isGameOver(false, 3, 3)).toBe(false)
  })

  it('a 1-1 draw over two rounds is a tie that needs a tie breaker', () => {
    const wins = countRoundWins(roundsSoFar([full(5, 0)], full(0, 5)))
    expect(wins).toEqual({ p1: 1, p2: 1 })
    expect(isGameOver(true, 2, 2)).toBe(true)
    expect(outcome(wins.p1, wins.p2)).toBe('tie')
  })

  it('all rounds level is a tie too', () => {
    const wins = countRoundWins([full(3, 3), full(3, 3), full(3, 3)])
    expect(outcome(wins.p1, wins.p2)).toBe('tie')
  })
})

describe('results table rows', () => {
  it('shows completed, live and pending rounds', () => {
    const rows = roundRows([full(10, 4)], round([3, null, null, null, null], [1, null, null, null, null]), 2, 3)
    expect(rows).toEqual([
      { round: 1, t1: 10, t2: 4, status: 'p1' },
      { round: 2, t1: 3, t2: 1, status: 'in-progress' },
      { round: 3, t1: null, t2: null, status: 'pending' },
    ])
  })

  it('marks the live round with its result once complete', () => {
    const rows = roundRows([], full(2, 2), 1, 1)
    expect(rows).toEqual([{ round: 1, t1: 2, t2: 2, status: 'tie' }])
  })
})

describe('sides', () => {
  it('swap every round but not in the tie breaker', () => {
    expect(sidesSwapped(1, false)).toBe(false)
    expect(sidesSwapped(2, false)).toBe(true)
    expect(sidesSwapped(3, false)).toBe(false)
    expect(sidesSwapped(2, true)).toBe(false)
  })
})

describe('placing a score', () => {
  it('fills the first empty slot', () => {
    const slots = s(3, null, null, null, null)
    expect(placeScore(slots, { value: 5 }, null)).toEqual({ index: 1, previous: null })
    expect(slots[1]).toEqual({ value: 5 })
  })

  it('replaces a selected slot and returns what was there', () => {
    const slots = s(3, 1, null, null, null)
    const result = placeScore(slots, { value: 0, drop: true }, 0)
    expect(result).toEqual({ index: 0, previous: { value: 3 } })
    expect(slots[0]).toEqual({ value: 0, drop: true })
  })

  it('refuses when the round is full', () => {
    const slots = s(1, 1, 1, 1, 1)
    expect(placeScore(slots, { value: 5 }, null)).toBeNull()
  })
})

describe('scoring pads', () => {
  const base: PadState = { ghostSide: null, selected: null, reviewing: false, tiebreak: null, throws1: 0, throws2: 0 }

  it('alternate throws: the side that is ahead waits', () => {
    expect(isPadDisabled(1, base)).toBe(false)
    expect(isPadDisabled(2, base)).toBe(false)
    expect(isPadDisabled(1, { ...base, throws1: 1 })).toBe(true)
    expect(isPadDisabled(2, { ...base, throws1: 1 })).toBe(false)
    expect(isPadDisabled(2, { ...base, throws2: 3, throws1: 2 })).toBe(true)
  })

  it('the ghost side is always disabled, even when selected', () => {
    expect(isPadDisabled(2, { ...base, ghostSide: 2, selected: { player: 2, index: 0 } })).toBe(true)
  })

  it('editing a selected score or reviewing a past round ignores turn order', () => {
    expect(isPadDisabled(1, { ...base, throws1: 3, throws2: 2, selected: { player: 1, index: 0 } })).toBe(false)
    expect(isPadDisabled(1, { ...base, throws1: 3, throws2: 2, reviewing: true })).toBe(false)
  })

  it('in a tie breaker a side locks once it has thrown this attempt', () => {
    const tb = newTiebreak()
    tb.s1[0] = { value: 5 }
    expect(isPadDisabled(1, { ...base, tiebreak: tb })).toBe(true)
    expect(isPadDisabled(2, { ...base, tiebreak: tb })).toBe(false)
  })

  it('clutch is available on the final (fifth) throw', () => {
    expect(isClutchAvailable(1, { ...base, throws1: 3 })).toBe(false)
    expect(isClutchAvailable(1, { ...base, throws1: 4 })).toBe(true)
    expect(isClutchAvailable(2, { ...base, throws1: 4, throws2: 3 })).toBe(false)
  })

  it('clutch stays available when replacing the final throw', () => {
    expect(isClutchAvailable(1, { ...base, throws1: 5, selected: { player: 1, index: 4 } })).toBe(true)
    expect(isClutchAvailable(1, { ...base, throws1: 5, selected: { player: 1, index: 3 } })).toBe(false)
  })

  it('clutch is always available while reviewing a past round', () => {
    expect(isClutchAvailable(1, { ...base, reviewing: true })).toBe(true)
  })

  it('in a tie breaker clutch follows the phase', () => {
    const tb = newTiebreak()
    expect(isClutchAvailable(1, { ...base, tiebreak: tb, throws1: 4 })).toBe(false)
    tb.phase = 'clutch'
    expect(isClutchAvailable(1, { ...base, tiebreak: tb })).toBe(true)
  })

  it('a decided tie breaker no longer gates the pads', () => {
    const tb: Tiebreak = { ...newTiebreak(), winner: 1 }
    expect(isPadDisabled(1, { ...base, tiebreak: tb, throws1: 1 })).toBe(true) // back to turn order
    expect(isClutchAvailable(1, { ...base, tiebreak: tb, throws1: 4 })).toBe(true)
  })
})

describe('tie breaker', () => {
  /** Throw one attempt for both sides and resolve it. */
  function attempt(tb: Tiebreak, v1: number, v2: number) {
    expect(recordTiebreakThrow(tb, 1, { value: v1 })).toBe(true)
    expect(resolveTiebreakAttempt(tb)).toBe('pending')
    expect(recordTiebreakThrow(tb, 2, { value: v2 })).toBe(true)
    return resolveTiebreakAttempt(tb)
  }

  it('starts at bulls with one open attempt', () => {
    const tb = newTiebreak()
    expect(tb).toEqual({ phase: 'bull', s1: [null], s2: [null], missedClutchRounds: 0, winner: null })
    expect(isTiebreakActive(tb)).toBe(true)
    expect(tiebreakSequence(3, tb)).toBe(4)
  })

  it('the higher throw wins', () => {
    const tb = newTiebreak()
    expect(attempt(tb, 3, 5)).toBe('decided')
    expect(tb.winner).toBe(2)
    expect(isTiebreakActive(tb)).toBe(false)
  })

  it('accepts one throw per side per attempt, and nothing once decided', () => {
    const tb = newTiebreak()
    expect(recordTiebreakThrow(tb, 1, { value: 5 })).toBe(true)
    expect(tiebreakThrown(tb, 1)).toBe(true)
    expect(tiebreakThrown(tb, 2)).toBe(false)
    expect(recordTiebreakThrow(tb, 1, { value: 3 })).toBe(false)
    expect(tb.s1).toEqual([{ value: 5 }])
    recordTiebreakThrow(tb, 2, { value: 1 })
    resolveTiebreakAttempt(tb)
    expect(recordTiebreakThrow(tb, 1, { value: 5 })).toBe(false)
  })

  it('level non-bulls stay at bulls and open the next attempt', () => {
    const tb = newTiebreak()
    expect(attempt(tb, 3, 3)).toBe('next')
    expect(tb.phase).toBe('bull')
    expect(tb.s1).toHaveLength(2)
    expect(tb.s1[1]).toBeNull()
    expect(tiebreakSequence(3, tb)).toBe(5)
  })

  it('both sticking bulls goes up to clutch', () => {
    const tb = newTiebreak()
    expect(attempt(tb, 5, 5)).toBe('next')
    expect(tb.phase).toBe('clutch')
  })

  it('both landing clutch stays at clutch and resets the miss count', () => {
    const tb = newTiebreak()
    attempt(tb, 5, 5)
    attempt(tb, 0, 0)
    expect(tb.missedClutchRounds).toBe(1)
    attempt(tb, 7, 7)
    expect(tb.phase).toBe('clutch')
    expect(tb.missedClutchRounds).toBe(0)
  })

  it('three both-missed clutch attempts in a row drop back to bulls', () => {
    const tb = newTiebreak()
    attempt(tb, 5, 5)
    attempt(tb, 0, 0)
    attempt(tb, 0, 0)
    expect(tb.phase).toBe('clutch')
    attempt(tb, 0, 0)
    expect(tb.phase).toBe('bull')
    expect(tb.missedClutchRounds).toBe(0)
    // ...and both bulls again goes back up
    attempt(tb, 5, 5)
    expect(tb.phase).toBe('clutch')
  })

  it('a clutch hit against a miss wins', () => {
    const tb = newTiebreak()
    attempt(tb, 5, 5)
    expect(attempt(tb, 0, 7)).toBe('decided')
    expect(tb.winner).toBe(2)
    expect(tb.s1).toHaveLength(2) // no further attempt opened
  })
})

describe('restoring a match from the server', () => {
  let clock = 0
  const t = (roundId: string, playerId: string, points: number, extra: Partial<ApiThrow> = {}): ApiThrow => ({
    throw_id: `t${++clock}`,
    timestamp: `2026-01-01T00:00:${String(clock).padStart(2, '0')}`,
    player_id: playerId,
    round_id: roundId,
    match_id: 'm',
    points,
    is_drop: false,
    ...extra,
  })
  const five = (roundId: string, playerId: string, points: number) =>
    Array.from({ length: 5 }, () => t(roundId, playerId, points))

  it('starts fresh with no rounds', () => {
    expect(restoreMatch({}, [], 'a', 'b', 3)).toEqual({
      completed: [],
      currentRound: 1,
      scores1: emptyRound(),
      scores2: emptyRound(),
    })
  })

  it('complete rounds become completed; the first incomplete one is live', () => {
    const throws = [...five('r1', 'a', 3), ...five('r1', 'b', 1), t('r2', 'a', 5), t('r2', 'b', 0, { is_drop: true })]
    const restored = restoreMatch({ 1: 'r1', 2: 'r2' }, throws, 'a', 'b', 3)
    expect(restored.completed).toHaveLength(1)
    expect(roundTotal(restored.completed[0]!.scores1)).toBe(15)
    expect(restored.currentRound).toBe(2)
    expect(restored.scores1[0]).toMatchObject({ value: 5, drop: false })
    expect(restored.scores2[0]).toMatchObject({ value: 0, drop: true })
    expect(restored.scores1[1]).toBeNull()
  })

  it('keeps the throw id so a restored throw can be replaced', () => {
    const throws = [t('r1', 'a', 3)]
    const restored = restoreMatch({ 1: 'r1' }, throws, 'a', 'b', 3)
    expect(restored.scores1[0]).toEqual({ value: 3, drop: false, throwId: throws[0]!.throw_id })
  })

  it('orders throws by timestamp, not arrival order', () => {
    const early = t('r1', 'a', 1)
    const late = t('r1', 'a', 5)
    const restored = restoreMatch({ 1: 'r1' }, [late, early], 'a', 'b', 3)
    expect(restored.scores1.map(x => x?.value ?? null)).toEqual([1, 5, null, null, null])
  })

  it('a round with no saved round is live even if later ones exist', () => {
    const restored = restoreMatch({ 2: 'r2' }, five('r2', 'a', 1), 'a', 'b', 3)
    expect(restored.currentRound).toBe(1)
    expect(restored.scores1).toEqual(emptyRound())
  })

  it('the last scheduled round stays live even when complete', () => {
    const throws = [...five('r1', 'a', 1), ...five('r1', 'b', 1), ...five('r2', 'a', 1), ...five('r2', 'b', 0)]
    const restored = restoreMatch({ 1: 'r1', 2: 'r2' }, throws, 'a', 'b', 2)
    expect(restored.completed).toHaveLength(1)
    expect(restored.currentRound).toBe(2)
    expect(isRoundComplete(restored.scores1, restored.scores2)).toBe(true)
  })

  it('ignores throws by other players, extra throws, and tie-break rounds', () => {
    const throws = [...five('r1', 'a', 1), t('r1', 'a', 5), t('r1', 'zed', 5), t('r3', 'a', 5)]
    const restored = restoreMatch({ 1: 'r1', 3: 'r3' }, throws, 'a', 'b', 2)
    expect(restored.currentRound).toBe(1)
    expect(roundTotal(restored.scores1)).toBe(5)
    expect(restored.scores2).toEqual(emptyRound())
  })
})
