import { describe, expect, it } from 'vitest'
import type { ApiMatch } from '../api'
import { displayPlayer, isDelayedByLate, matchLabel, matchStatus, sortForMatchList } from '../eventMatches'

const match = (sequence: number, p1: string | null, p2: string | null, extra: Partial<ApiMatch> = {}): ApiMatch => ({
  match_id: `m${sequence}`,
  event_id: 'e',
  player_1_id: p1,
  player_2_id: p2,
  sequence,
  match_type: 'swiss',
  rounds_per_match: 2,
  bracket_round: null,
  bracket_slot: null,
  winner_id: null,
  timestamp: '2026-01-01T00:00:00',
  is_locked: false,
  locked_by: null,
  is_finished: false,
  ...extra,
})

describe('group-stage match list order', () => {
  it('puts upcoming first, late throwers next, finished last, each in schedule order', () => {
    const matches = [
      match(1, 'a', 'b', { is_finished: true }),
      match(2, 'c', 'late'),
      match(3, 'a', 'c'),
      match(4, 'late', 'b', { is_finished: true }),
      match(5, 'b', 'c'),
    ]
    expect(sortForMatchList(matches, ['late']).map(m => m.sequence)).toEqual([3, 5, 2, 1, 4])
  })

  it('does not reorder the input array', () => {
    const matches = [match(2, 'a', 'b'), match(1, 'a', 'b')]
    sortForMatchList(matches, [])
    expect(matches.map(m => m.sequence)).toEqual([2, 1])
  })

  it('flags only unfinished matches with a late thrower', () => {
    expect(isDelayedByLate(match(1, 'a', 'late'), ['late'])).toBe(true)
    expect(isDelayedByLate(match(1, 'a', 'late', { is_finished: true }), ['late'])).toBe(false)
    expect(isDelayedByLate(match(1, 'a', 'b'), ['late'])).toBe(false)
  })
})

describe('match labels', () => {
  it('shows TBD for undecided players and Ghost for the ghost', () => {
    expect(displayPlayer(null)).toBe('TBD')
    expect(displayPlayer('__ghost__')).toBe('Ghost')
    expect(matchLabel(match(1, 'Ann', null))).toBe('Ann vs TBD')
  })

  it('status: finished beats locked beats open', () => {
    expect(matchStatus(match(1, 'a', 'b', { is_finished: true, is_locked: true }))).toBe('finished')
    expect(matchStatus(match(1, 'a', 'b', { is_locked: true }))).toBe('locked')
    expect(matchStatus(match(1, 'a', 'b'))).toBe('open')
  })
})
