// Mirrors the live match to the TV scoreboard: through BroadcastChannel and
// localStorage for a TV on the same device, and through PUT /tv/snapshot for a
// TV on another one (the iPad is AirPlayed, or a second screen polls the API).
// Best-effort by design: a failed publish never interrupts scoring.

import { computed, ref, watch } from 'vue'
import { getMatchesByEvent, putTvSnapshot } from '../api'
import { publishTvSnapshot, type TvSnapshot } from '../displaySync'
import { nextUpMatch } from '../nextMatch'
import { THROWS, sidesSwapped as sidesSwappedFor, type Slot } from '../scoring/rules'
import { arenaLabel } from '../venue'
import type { useMatchScoring, ScoringProps } from './useMatchScoring'
import type { MatchSync } from './useMatchSync'

type Scoring = ReturnType<typeof useMatchScoring>

function packThrows(scores: Slot[]): TvSnapshot['leftScores'] {
  return scores.map(entry => (entry ? { value: entry.value, drop: !!entry.drop } : null))
}

// The tie breaker keeps the five-slot look; extra attempts pad past it
function padTiebreak(arr: Slot[]): Slot[] {
  return arr.length >= THROWS ? arr : [...arr, ...Array<Slot>(THROWS - arr.length).fill(null)]
}

export function useTvPublisher(props: ScoringProps, scoring: Scoring, sync: MatchSync) {
  const nextMatch = ref<TvSnapshot['nextMatch']>(null)

  // Only tease the next match once this one is well underway
  const nextMatchReady = computed(() =>
    scoring.completedRounds.value.length >= 2
    || (scoring.currentRound.value >= 2 && scoring.roundComplete.value)
  )

  async function refreshNextMatch() {
    const eventId = props.matchContext?.eventId
    if (!eventId) {
      nextMatch.value = null
      return
    }
    try {
      const upcoming = nextUpMatch(await getMatchesByEvent(eventId), sync.matchId.value)
      nextMatch.value = upcoming
        ? { player1: upcoming.player_1_id ?? '', player2: upcoming.player_2_id ?? '' }
        : null
    } catch (e) {
      console.error(`Failed to look up the next match for event ${eventId}`, e)
      nextMatch.value = null
    }
  }

  function publish() {
    const tb = scoring.tiebreak.value
    const inTiebreak = scoring.showTiebreak.value && !!tb
    const swapped = sidesSwappedFor(scoring.currentRound.value, inTiebreak)
    const s1 = inTiebreak ? padTiebreak(tb.s1) : scoring.scores1.value
    const s2 = inTiebreak ? padTiebreak(tb.s2) : scoring.scores2.value
    const payload: Omit<TvSnapshot, 'updatedAt'> = {
      player1Name: props.player1Name,
      player2Name: props.player2Name,
      leftName: swapped ? props.player2Name : props.player1Name,
      rightName: swapped ? props.player1Name : props.player2Name,
      leftScores: packThrows(swapped ? s2 : s1),
      rightScores: packThrows(swapped ? s1 : s2),
      totalRounds: props.totalRounds,
      displayRound: scoring.currentRound.value,
      roundRows: scoring.allRoundRows.value,
      eventName: props.matchContext?.eventName ?? '',
      arenaLabel: props.matchContext?.arenaIds?.length
        ? arenaLabel(props.matchContext.arenaIds)
        : (props.matchContext?.arenaLabel ?? ''),
      gameWinner: scoring.gameWinner.value,
      showTiebreak: scoring.showTiebreak.value,
      nextMatch: nextMatchReady.value ? nextMatch.value : null,
    }
    publishTvSnapshot(payload)
    // Best-effort mirror for TVs on another device; scoring must not depend on it
    putTvSnapshot(payload).catch(() => {})
  }

  watch(
    [
      () => props.player1Name, () => props.player2Name, () => props.totalRounds, () => props.matchContext,
      scoring.currentRound, scoring.scores1, scoring.scores2, scoring.completedRounds, scoring.tiebreak,
      scoring.showTiebreak, scoring.gameWinner, scoring.allRoundRows, nextMatch, nextMatchReady,
    ],
    publish,
    { deep: true },
  )

  watch(() => props.matchContext?.eventId, refreshNextMatch, { immediate: true })
}
