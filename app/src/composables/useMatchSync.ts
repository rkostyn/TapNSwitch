// Server sync for the match on the scoreboard: rounds are created on demand,
// each placed score is saved as a throw (an edit deletes the old throw first),
// and an event match is rebuilt from the server when it is opened. Casual
// matches (no MatchContext) never touch the server.

import { ref } from 'vue'
import {
  apiErrorMessage,
  deleteThrow,
  finishMatch,
  getRoundsByMatch,
  getThrows,
  startRound,
  submitThrow,
  type ApiThrow,
} from '../api'
import { releaseMatch } from '../matchLock'
import type { MatchContext } from '../match'
import type { PlayerSide, ScoreEntry, Slot } from '../scoring/types'

export function useMatchSync(context: () => MatchContext | null) {
  // Generated once per casual match; the event match id when one is selected
  const matchId = ref<string>(crypto.randomUUID())
  const roundIdBySeq = ref<Record<number, string>>({}) // round sequence -> round_id on the server
  const syncError = ref('')
  const finishing = ref(false)

  function clear() {
    roundIdBySeq.value = {}
    syncError.value = ''
  }

  async function ensureRound(seq: number) {
    const ctx = context()
    if (!ctx || roundIdBySeq.value[seq]) return
    // Finished matches can't grow new rounds — only existing ones are editable
    if (ctx.isFinished) return
    const round = await startRound(matchId.value, ctx.player1Id, ctx.player2Id, seq)
    roundIdBySeq.value = { ...roundIdBySeq.value, [seq]: round.round_id }
  }

  /** Create a round without waiting; a failure shows `message` in the sync banner. */
  function startRoundInBackground(seq: number, message: string) {
    ensureRound(seq).catch(e => {
      console.error(`Failed to start round ${seq} of match ${matchId.value}`, e)
      syncError.value = message
    })
  }

  /** Persist a placed/edited score; `entry.throwId` is set once saved. */
  async function saveThrow(entry: ScoreEntry, player: PlayerSide, oldEntry: Slot | undefined, roundSeq: number) {
    const ctx = context()
    if (!ctx) return
    try {
      syncError.value = ''
      if (oldEntry?.throwId) await deleteThrow(oldEntry.throwId)
      await ensureRound(roundSeq)
      const roundId = roundIdBySeq.value[roundSeq]
      if (!roundId) {
        syncError.value = 'This round does not exist on the server.'
        return
      }
      entry.throwId = await submitThrow({
        playerId: player === 1 ? ctx.player1Id : ctx.player2Id,
        roundId,
        matchId: matchId.value,
        eventId: ctx.eventId,
        points: entry.value,
        isDrop: !!entry.drop,
        clutchCalled: !!entry.clutch,
      })
    } catch (e) {
      console.error(`Failed to save a throw for round ${roundSeq} of match ${matchId.value}`, e)
      syncError.value = 'Score was not saved to the server.'
    }
  }

  /** Delete a cleared score's throw without waiting. */
  function removeThrow(old: Slot | undefined) {
    if (!context() || !old?.throwId) return
    const throwId = old.throwId
    deleteThrow(throwId).catch(e => {
      console.error(`Failed to delete throw ${throwId}`, e)
      syncError.value = 'Score was not removed on the server.'
    })
  }

  /**
   * Load an event match's rounds and throws. `restore` rebuilds local state
   * from the throws and returns the live round number, which is then made
   * to exist on the server.
   */
  async function load(ctx: MatchContext, restore: (throws: ApiThrow[], roundIdBySeq: Record<number, string>) => number) {
    try {
      const rounds = await getRoundsByMatch(ctx.matchId)
      const map: Record<number, string> = {}
      for (const r of rounds) map[r.sequence] = r.round_id
      roundIdBySeq.value = map
      const throws = await getThrows({ matchId: ctx.matchId })
      const liveRound = restore(throws, roundIdBySeq.value)
      await ensureRound(liveRound)
    } catch (e) {
      console.error(`Failed to load match ${ctx.matchId} from the server`, e)
      syncError.value = 'Could not sync this match with the server.'
    }
  }

  /** Finish the event match and release its lock. Resolves true on success. */
  async function finish(): Promise<boolean> {
    finishing.value = true
    syncError.value = ''
    try {
      await finishMatch(matchId.value)
      await releaseMatch(matchId.value)
      return true
    } catch (e) {
      console.error(`Failed to finish match ${matchId.value}`, e)
      syncError.value = apiErrorMessage(e, 'Failed to finish the match.')
      return false
    } finally {
      finishing.value = false
    }
  }

  /**
   * Leave a finished match after editing its scores — the API recomputes the
   * winner on every edit, so there is nothing to re-finish.
   */
  async function leave() {
    await releaseMatch(matchId.value)
  }

  return {
    matchId,
    roundIdBySeq,
    syncError,
    finishing,
    clear,
    ensureRound,
    startRoundInBackground,
    saveThrow,
    removeThrow,
    load,
    finish,
    leave,
  }
}

export type MatchSync = ReturnType<typeof useMatchSync>
