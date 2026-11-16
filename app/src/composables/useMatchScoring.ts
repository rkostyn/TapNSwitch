// Local game state for the match on the scoreboard: the live round, completed
// rounds, a round under review, a selected score being replaced, and the tie
// breaker. Rules come from scoring/rules; every change is handed to the
// server sync, which ignores it for casual matches.

import { computed, ref } from 'vue'
import { GHOST_PLAYER_ID } from '../config'
import type { MatchContext } from '../match'
import {
  THROWS,
  countRoundWins,
  emptyRound,
  hasClinched,
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
  roundsSoFar,
  sidesSwapped as sidesSwappedFor,
  throwCount,
  tiebreakSequence,
  type PadState,
  type PlayerSide,
  type RoundScores,
  type ScoreEntry,
  type ScorePayload,
  type Slot,
  type Tiebreak,
} from '../scoring/rules'
import type { MatchSync } from './useMatchSync'

export interface ScoringProps {
  player1Name: string
  player2Name: string
  totalRounds: number
  matchContext: MatchContext | null
}

export function useMatchScoring(props: ScoringProps, sync: MatchSync) {
  const currentRound = ref(1)
  const scores1 = ref<Slot[]>(emptyRound())
  const scores2 = ref<Slot[]>(emptyRound())
  const completedRounds = ref<RoundScores[]>([])
  const selected = ref<{ player: PlayerSide; index: number } | null>(null)
  // A previously played round selected for review/editing; null = live round
  const viewedRound = ref<number | null>(null)
  const tiebreak = ref<Tiebreak | null>(null)

  const displayRound = computed(() => viewedRound.value ?? currentRound.value)

  // --- Tie breaker state ---------------------------------------------------
  const tiebreakActive = computed(() => isTiebreakActive(tiebreak.value))
  // The tie breaker plays out in the main score grid rather than a separate box,
  // unless the user has stepped away to review an earlier round.
  const showTiebreak = computed(() => !!tiebreak.value && !viewedRound.value)
  const tiebreakInProgress = computed(() => showTiebreak.value && !tiebreak.value?.winner)

  // --- What the grid shows -------------------------------------------------
  // The tie breaker keeps the familiar five-slot look; extra attempts pad past it
  const padTiebreak = (arr: Slot[]): Slot[] =>
    arr.length >= THROWS ? arr : [...arr, ...Array<Slot>(THROWS - arr.length).fill(null)]

  // The round under review; viewRound only ever selects a completed round
  const viewedScores = computed(() =>
    viewedRound.value ? completedRounds.value[viewedRound.value - 1] ?? null : null
  )

  const displayScores1 = computed(() =>
    showTiebreak.value && tiebreak.value ? padTiebreak(tiebreak.value.s1)
    : viewedScores.value ? viewedScores.value.scores1
    : scores1.value
  )
  const displayScores2 = computed(() =>
    showTiebreak.value && tiebreak.value ? padTiebreak(tiebreak.value.s2)
    : viewedScores.value ? viewedScores.value.scores2
    : scores2.value
  )

  const sidesSwapped = computed(() => sidesSwappedFor(displayRound.value, showTiebreak.value))

  // Rows in the score grid: five per normal round. The tie breaker shows five
  // slots too, growing (and scrolling) only once sudden death runs past them.
  const slotCount = computed(() =>
    showTiebreak.value && tiebreak.value ? Math.max(THROWS, tiebreak.value.s1.length) : THROWS
  )

  // Solo (ghost) match: one side is the ghost, which scores 0 on every throw.
  // It is filled automatically whenever the real player throws, never by hand.
  const ghostSide = computed<PlayerSide | null>(() =>
    props.matchContext?.player1Id === GHOST_PLAYER_ID ? 1
    : props.matchContext?.player2Id === GHOST_PLAYER_ID ? 2
    : null
  )

  // --- Live round and match result ----------------------------------------
  const roundComplete = computed(() => isRoundComplete(scores1.value, scores2.value))
  const throws1 = computed(() => throwCount(scores1.value))
  const throws2 = computed(() => throwCount(scores2.value))
  const player1Disabled = computed(() => throws1.value > throws2.value)
  const player2Disabled = computed(() => throws2.value > throws1.value)

  // Rounds won so far (the live round counts once it is complete). A majority
  // clinches the best-of match — 3 of 5, 4 of 7, etc.
  const roundWins = computed(() =>
    countRoundWins(roundsSoFar(completedRounds.value, { scores1: scores1.value, scores2: scores2.value }))
  )
  const clinched = computed(() => hasClinched(roundWins.value, props.totalRounds))
  const gameOver = computed(() =>
    isGameOver(roundComplete.value, currentRound.value, props.totalRounds, clinched.value)
  )

  const allRoundRows = computed(() =>
    roundRows(completedRounds.value, { scores1: scores1.value, scores2: scores2.value }, currentRound.value, props.totalRounds)
  )

  const playerName = (player: PlayerSide) => (player === 1 ? props.player1Name : props.player2Name)

  /** Once the game is over: the name of whoever took more rounds, or 'tie'. */
  const overallWinner = computed(() => {
    if (!gameOver.value) return null
    const result = outcome(roundWins.value.p1, roundWins.value.p2)
    return result === 'p1' ? props.player1Name : result === 'p2' ? props.player2Name : 'tie'
  })

  const needsTiebreak = computed(() =>
    gameOver.value && overallWinner.value === 'tie' && !props.matchContext?.isFinished
  )

  // The game's winner once it's over — the tie breaker's winner when the rounds
  // ended level, otherwise whoever took more rounds. Null until the game ends.
  const gameWinner = computed(() =>
    tiebreak.value?.winner ? playerName(tiebreak.value.winner)
    : overallWinner.value !== 'tie' ? overallWinner.value
    : null
  )

  // A tied game cannot be finished until the tie breaker settles it
  const tieUnresolved = computed(() =>
    gameOver.value && overallWinner.value === 'tie' && !tiebreak.value?.winner
  )

  // --- Pads -----------------------------------------------------------------
  const padState = computed<PadState>(() => ({
    ghostSide: ghostSide.value,
    selected: selected.value,
    reviewing: !!viewedRound.value,
    tiebreak: tiebreak.value,
    throws1: throws1.value,
    throws2: throws2.value,
  }))
  const padDisabled = (player: PlayerSide) => isPadDisabled(player, padState.value)
  const clutchAvailable = (player: PlayerSide) => isClutchAvailable(player, padState.value)

  // --- Actions --------------------------------------------------------------
  const TIEBREAK_ROUND_ERROR = 'Could not start the tie-breaker round on the server.'

  function startTiebreak() {
    tiebreak.value = newTiebreak()
    sync.startRoundInBackground(tiebreakSequence(props.totalRounds, tiebreak.value), TIEBREAK_ROUND_ERROR)
  }

  function tiebreakScore(player: PlayerSide, payload: ScorePayload) {
    const tb = tiebreak.value
    if (!tb) return
    const entry: ScoreEntry = { value: payload.points, clutch: !!payload.clutch, drop: !!payload.drop }
    if (!recordTiebreakThrow(tb, player, entry)) return
    sync.saveThrow(entry, player, null, tiebreakSequence(props.totalRounds, tb))
    if (resolveTiebreakAttempt(tb) === 'next') {
      sync.startRoundInBackground(tiebreakSequence(props.totalRounds, tb), TIEBREAK_ROUND_ERROR)
    }
  }

  function applyScore(player: PlayerSide, payload: ScorePayload) {
    if (!payload || typeof payload.points !== 'number') return
    const entry: ScoreEntry = { value: payload.points, clutch: !!payload.clutch, drop: !!payload.drop }
    const arr = player === 1 ? displayScores1.value : displayScores2.value
    const replacing = selected.value?.player === player ? selected.value.index : null
    const placed = placeScore(arr, entry, replacing)
    if (!placed) return
    if (replacing !== null) selected.value = null
    sync.saveThrow(entry, player, placed.previous, displayRound.value)
    // In a ghost match the opponent doesn't throw — mirror a 0 into the ghost's
    // matching slot so the round fills and completes normally.
    if (ghostSide.value !== null && player !== ghostSide.value) fillGhost(placed.index)
  }

  function fillGhost(index: number) {
    const g = ghostSide.value
    if (g === null) return
    const arr = g === 1 ? displayScores1.value : displayScores2.value
    if (arr[index] !== null) return
    const entry: ScoreEntry = { value: 0, clutch: false }
    arr[index] = entry
    sync.saveThrow(entry, g, null, displayRound.value)
  }

  // The score panels do double duty: during a tie breaker they record the
  // sudden-death throws; otherwise they score the round on display.
  function score(player: PlayerSide, payload: ScorePayload) {
    if (tiebreakActive.value && !viewedRound.value && !selected.value) tiebreakScore(player, payload)
    else applyScore(player, payload)
  }

  function clearScore(player: PlayerSide, index: number) {
    const arr = player === 1 ? displayScores1.value : displayScores2.value
    const old = arr[index]
    arr[index] = null
    sync.removeThrow(old)
  }

  function nextRound() {
    completedRounds.value.push({ scores1: [...scores1.value], scores2: [...scores2.value] })
    currentRound.value++
    scores1.value = emptyRound()
    scores2.value = emptyRound()
    selected.value = null
    viewedRound.value = null
    sync.startRoundInBackground(currentRound.value, 'Could not start the round on the server.')
  }

  // Click a round in the results table to review/edit it, even after the match ended
  function viewRound(roundNum: number) {
    if (roundNum > currentRound.value) return
    selected.value = null
    viewedRound.value = roundNum === currentRound.value ? null : roundNum
  }

  // Score cell helpers
  function selectScore(player: PlayerSide, index: number) {
    if (showTiebreak.value) return // tie-break throws aren't individually editable
    selected.value = { player, index }
  }

  function confirmReset() {
    if (!selected.value) return
    clearScore(selected.value.player, selected.value.index)
    selected.value = null
  }

  function isSelected(player: PlayerSide, index: number) {
    return selected.value?.player === player && selected.value?.index === index
  }

  function clear() {
    currentRound.value = 1
    scores1.value = emptyRound()
    scores2.value = emptyRound()
    completedRounds.value = []
    selected.value = null
    viewedRound.value = null
    sync.clear()
    tiebreak.value = null
  }

  /** Start over: a fresh casual match, or the selected event match rebuilt from the server. */
  async function reset() {
    clear()
    const ctx = props.matchContext
    if (!ctx) {
      sync.matchId.value = crypto.randomUUID()
      return
    }
    sync.matchId.value = ctx.matchId
    await sync.load(ctx, (throws, roundIdBySeq) => {
      const restored = restoreMatch(roundIdBySeq, throws, ctx.player1Id, ctx.player2Id, props.totalRounds)
      completedRounds.value = restored.completed
      currentRound.value = restored.currentRound
      scores1.value = restored.scores1
      scores2.value = restored.scores2
      return currentRound.value
    })
  }

  return {
    // state
    currentRound,
    viewedRound,
    tiebreak,
    displayRound,
    displayScores1,
    displayScores2,
    sidesSwapped,
    slotCount,
    showTiebreak,
    tiebreakInProgress,
    roundComplete,
    player1Disabled,
    player2Disabled,
    gameOver,
    allRoundRows,
    needsTiebreak,
    gameWinner,
    tieUnresolved,
    padDisabled,
    clutchAvailable,
    // actions
    score,
    startTiebreak,
    nextRound,
    viewRound,
    selectScore,
    confirmReset,
    isSelected,
    reset,
  }
}
