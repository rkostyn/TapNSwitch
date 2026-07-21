<script setup>
  import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
  import UrbanScore from './UrbanScore.vue'
  import TvScoreOverlay from './TvScoreOverlay.vue'
  import { GHOST_PLAYER_ID } from '../config'
  import {
    startRound as apiStartRound,
    submitThrow,
    deleteThrow,
    getThrows,
    getRoundsByMatch,
    finishMatch,
    unlockMatch,
  } from '../api'

  const props = defineProps(['player1Name', 'player2Name', 'totalRounds', 'matchContext'])
  const emit = defineEmits(['resetScore', 'select', 'deselect', 'requestConfig', 'matchDone', 'tvOverlayChange'])

  const tvOverlayOpen = ref(false)

  const THROWS = 5

  // Match ID — generated once per casual match; the event match id when one is selected
  const matchId = ref(crypto.randomUUID())

  // Game state
  const currentRound = ref(1)
  const activeTab = ref('p1')
  const scores1 = ref(Array(THROWS).fill(null))
  const scores2 = ref(Array(THROWS).fill(null))
  const completedRounds = ref([])
  const selected = ref(null) // { player: 1|2, index: number }

  // A previously played round selected for review/editing; null = live round
  const viewedRound = ref(null)

  // Event-match sync state
  const roundIdBySeq = ref({}) // round sequence -> round_id on the server
  const syncError = ref('')
  const finishing = ref(false)

  // Scroll container for the score lines — kept pinned to the bottom as tie-break
  // attempts pile up past the visible five slots
  const rowsEl = ref(null)

  const displayRound = computed(() => viewedRound.value ?? currentRound.value)

  const roundTitle = computed(() =>
    showTiebreak.value ? 'Tie Breaker' : `Round ${displayRound.value} of ${props.totalRounds}`
  )

  // The tie breaker keeps the familiar five-slot look; extra attempts pad past it
  const padTiebreak = (arr) =>
    arr.length >= THROWS ? arr : [...arr, ...Array(THROWS - arr.length).fill(null)]

  const displayScores1 = computed(() =>
    showTiebreak.value ? padTiebreak(tiebreak.value.s1)
    : viewedRound.value ? completedRounds.value[viewedRound.value - 1].scores1
    : scores1.value
  )
  const displayScores2 = computed(() =>
    showTiebreak.value ? padTiebreak(tiebreak.value.s2)
    : viewedRound.value ? completedRounds.value[viewedRound.value - 1].scores2
    : scores2.value
  )

  // Sides swap every round; the tie breaker keeps player 1 on the left throughout
  const sidesSwapped = computed(() => showTiebreak.value ? false : (displayRound.value - 1) % 2 === 1)

  // Rows in the score grid: five per normal round. The tie breaker shows five
  // slots too, growing (and scrolling) only once sudden death runs past them.
  const slotCount = computed(() =>
    showTiebreak.value ? Math.max(THROWS, tiebreak.value.s1.length) : THROWS
  )

  // Which player name/scores are on the left vs right panel for the displayed round
  const leftName = computed(() => sidesSwapped.value ? props.player2Name : props.player1Name)
  const rightName = computed(() => sidesSwapped.value ? props.player1Name : props.player2Name)
  const leftScores = computed(() => sidesSwapped.value ? displayScores2.value : displayScores1.value)
  const rightScores = computed(() => sidesSwapped.value ? displayScores1.value : displayScores2.value)
  const applyScoreLeft = (payload) => routeScore(sidesSwapped.value ? 2 : 1, payload)
  const applyScoreRight = (payload) => routeScore(sidesSwapped.value ? 1 : 2, payload)

  // The score panels do double duty: during a tie breaker they record the
  // sudden-death throws; otherwise they score the round on display.
  // payload = { points: number, clutch: boolean }
  function routeScore(player, payload) {
    if (tiebreakActive.value && !viewedRound.value && !selected.value) tiebreakScore(player, payload)
    else applyScore(player, payload)
  }

  // Solo (ghost) match: one side is the ghost, which scores 0 on every throw.
  // It is filled automatically whenever the real player throws, never by hand.
  const ghostSide = computed(() =>
    props.matchContext?.player1Id === GHOST_PLAYER_ID ? 1
    : props.matchContext?.player2Id === GHOST_PLAYER_ID ? 2
    : null
  )

  const roundComplete = computed(() => scores1.value.every(s => s !== null) && scores2.value.every(s => s !== null))

  const throws1 = computed(() => scores1.value.filter(s => s !== null).length)
  const throws2 = computed(() => scores2.value.filter(s => s !== null).length)
  const player1Disabled = computed(() => throws1.value > throws2.value)
  const player2Disabled = computed(() => throws2.value > throws1.value)
  const player1ClutchAvailable = computed(() => throws1.value === THROWS - 1)
  const player2ClutchAvailable = computed(() => throws2.value === THROWS - 1)
  const gameOver = computed(() => roundComplete.value && currentRound.value === props.totalRounds)

  // Alternating-throw rules only gate the live round; past rounds edit freely.
  // During a tie breaker a side locks once its throw for the current attempt is in.
  const tbEntered = (player) => {
    const tb = tiebreak.value
    if (!tb) return false
    const arr = player === 1 ? tb.s1 : tb.s2
    return arr[arr.length - 1] !== null
  }

  function sideDisabled(player) {
    if (player === ghostSide.value) return true // the ghost never throws by hand
    if (selected.value?.player === player) return false // editing a placed score
    if (viewedRound.value) return false
    if (tiebreakActive.value) return tbEntered(player)
    return player === 1 ? player1Disabled.value : player2Disabled.value
  }

  function sideClutchAvailable(player) {
    if (viewedRound.value) return true
    if (tiebreakActive.value) return tiebreak.value.phase === 'clutch'
    // Replacing the last and final throw? Clutch is still on the table.
    if (selected.value?.player === player && selected.value.index === THROWS - 1) return true
    return player === 1 ? player1ClutchAvailable.value : player2ClutchAvailable.value
  }

  const leftDisabled = computed(() => sideDisabled(sidesSwapped.value ? 2 : 1))
  const rightDisabled = computed(() => sideDisabled(sidesSwapped.value ? 1 : 2))
  const leftClutchAvailable = computed(() => sideClutchAvailable(sidesSwapped.value ? 2 : 1))
  const rightClutchAvailable = computed(() => sideClutchAvailable(sidesSwapped.value ? 1 : 2))

  const sum = arr => arr.reduce((a, s) => a + (s ? s.value : 0), 0)

  const allRoundRows = computed(() =>
    Array.from({ length: props.totalRounds }, (_, i) => {
      const roundNum = i + 1
      if (roundNum < currentRound.value) {
        const r = completedRounds.value[i]
        const t1 = sum(r.scores1), t2 = sum(r.scores2)
        return { round: roundNum, t1, t2, status: t1 > t2 ? 'p1' : t2 > t1 ? 'p2' : 'tie' }
      } else if (roundNum === currentRound.value) {
        const t1 = sum(scores1.value), t2 = sum(scores2.value)
        const done = roundComplete.value
        return { round: roundNum, t1, t2, status: done ? (t1 > t2 ? 'p1' : t2 > t1 ? 'p2' : 'tie') : 'in-progress' }
      } else {
        return { round: roundNum, t1: null, t2: null, status: 'pending' }
      }
    })
  )

  const overallWinner = computed(() => {
    if (!gameOver.value) return null
    const last = { scores1: scores1.value, scores2: scores2.value }
    const all = [...completedRounds.value, last]
    const wins1 = all.filter(r => sum(r.scores1) > sum(r.scores2)).length
    const wins2 = all.filter(r => sum(r.scores2) > sum(r.scores1)).length
    return wins1 > wins2 ? props.player1Name : wins2 > wins1 ? props.player2Name : 'tie'
  })

  // --- Tie breaker -----------------------------------------------------------
  // Equal rounds taken is a draw; sudden death settles it. One throw per side
  // at bulls; both sticking a bull goes up to clutch; three clutch rounds in a
  // row with neither hitting drops back down to bulls.
  const tiebreak = ref(null) // { phase, attempt, s1, s2, missedClutchRounds, winner }

  const needsTiebreak = computed(() =>
    gameOver.value && overallWinner.value === 'tie' && !props.matchContext?.isFinished
  )

  const tiebreakActive = computed(() => !!tiebreak.value && !tiebreak.value.winner)

  // The tie breaker plays out in the main score grid rather than a separate box,
  // unless the user has stepped away to review an earlier round.
  const showTiebreak = computed(() => !!tiebreak.value && !viewedRound.value)
  const tiebreakInProgress = computed(() => showTiebreak.value && !tiebreak.value.winner)

  // The game's winner once it's over — the tie breaker's winner when the rounds
  // ended level, otherwise whoever took more rounds. Null until the game ends.
  const gameWinner = computed(() =>
    tiebreak.value?.winner ?? (overallWinner.value !== 'tie' ? overallWinner.value : null)
  )

  // As sudden death adds slots, keep the newest attempt in view at the bottom
  watch(slotCount, () => {
    if (!showTiebreak.value) return
    nextTick(() => {
      if (rowsEl.value) rowsEl.value.scrollTop = rowsEl.value.scrollHeight
    })
  })

  // A tied game cannot be finished until the tie breaker settles it
  const tieUnresolved = computed(() =>
    gameOver.value && overallWinner.value === 'tie' && !tiebreak.value?.winner
  )

  // Each attempt is its own one-slot round on the server, sequenced after the
  // regular rounds. s1/s2 grow in lockstep, one entry per attempt.
  function tiebreakSeq() {
    return props.totalRounds + tiebreak.value.s1.length
  }

  function startTiebreak() {
    tiebreak.value = { phase: 'bull', s1: [null], s2: [null], missedClutchRounds: 0, winner: null }
    ensureRound(tiebreakSeq()).catch(() => { syncError.value = 'Could not start the tie-breaker round on the server.' })
  }

  function tiebreakScore(player, payload) {
    const tb = tiebreak.value
    if (!tb || tb.winner) return
    const arr = player === 1 ? tb.s1 : tb.s2
    const idx = arr.length - 1
    if (arr[idx] !== null) return
    const entry = { value: payload.points, clutch: payload.clutch }
    arr[idx] = entry
    syncEntry(entry, player, null, tiebreakSeq())
    if (tb.s1[idx] !== null && tb.s2[idx] !== null) resolveTiebreakAttempt()
  }

  function resolveTiebreakAttempt() {
    const tb = tiebreak.value
    const idx = tb.s1.length - 1
    const v1 = tb.s1[idx].value, v2 = tb.s2[idx].value
    if (v1 !== v2) {
      tb.winner = v1 > v2 ? props.player1Name : props.player2Name
      return
    }
    if (tb.phase === 'bull') {
      // Both stuck their bulls — they may go up for clutch
      if (v1 === 5) tb.phase = 'clutch'
    } else if (v1 > 0) {
      // Both landed a clutch — stay up for clutch
      tb.missedClutchRounds = 0
    } else {
      tb.missedClutchRounds++
      if (tb.missedClutchRounds >= 3) {
        tb.phase = 'bull'
        tb.missedClutchRounds = 0
      }
    }
    // Still tied — open a fresh slot for the next attempt
    tb.s1.push(null)
    tb.s2.push(null)
    ensureRound(tiebreakSeq()).catch(() => { syncError.value = 'Could not start the tie-breaker round on the server.' })
  }

  function applyScore(player, payload) {
    if (!payload || typeof payload.points !== 'number') return
    const entry = { value: payload.points, clutch: !!payload.clutch }

    const arr = player === 1 ? displayScores1.value : displayScores2.value
    let oldEntry = null
    let idx
    if (selected.value?.player === player) {
      idx = selected.value.index
      oldEntry = arr[idx]
      arr[idx] = entry
      selected.value = null
    } else {
      idx = arr.indexOf(null)
      if (idx === -1) return
      arr[idx] = entry
    }
    syncEntry(entry, player, oldEntry, displayRound.value)
    // In a ghost match the opponent doesn't throw — mirror a 0 into the ghost's
    // matching slot so the round fills and completes normally.
    if (ghostSide.value !== null && player !== ghostSide.value) fillGhost(idx)
  }

  function fillGhost(index) {
    const g = ghostSide.value
    const arr = g === 1 ? displayScores1.value : displayScores2.value
    if (arr[index] !== null) return
    const entry = { value: 0, clutch: false }
    arr[index] = entry
    syncEntry(entry, g, null, displayRound.value)
  }

  // Persist a placed/edited score to the API when scoring an event match
  async function syncEntry(entry, player, oldEntry, roundSeq) {
    const ctx = props.matchContext
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
      syncError.value = 'Score was not saved to the server.'
    }
  }

  async function ensureRound(seq) {
    const ctx = props.matchContext
    if (!ctx || roundIdBySeq.value[seq]) return
    // Finished matches can't grow new rounds — only existing ones are editable
    if (ctx.isFinished) return
    const round = await apiStartRound(matchId.value, ctx.player1Id, ctx.player2Id, seq)
    roundIdBySeq.value = { ...roundIdBySeq.value, [seq]: round.round_id }
  }

  function resetScore(player, index) {
    const arr = player === 1 ? displayScores1.value : displayScores2.value
    const old = arr[index]
    arr[index] = null
    if (props.matchContext && old?.throwId) {
      deleteThrow(old.throwId).catch(() => { syncError.value = 'Score was not removed on the server.' })
    }
  }

  function nextRound() {
    completedRounds.value.push({ scores1: [...scores1.value], scores2: [...scores2.value] })
    currentRound.value++
    scores1.value = Array(THROWS).fill(null)
    scores2.value = Array(THROWS).fill(null)
    selected.value = null
    viewedRound.value = null
    ensureRound(currentRound.value).catch(() => { syncError.value = 'Could not start the round on the server.' })
  }

  // Click a round in the results table to review/edit it, even after the match ended
  function viewRound(roundNum) {
    if (roundNum > currentRound.value) return
    selected.value = null
    viewedRound.value = roundNum === currentRound.value ? null : roundNum
  }

  function clearLocalState() {
    currentRound.value = 1
    scores1.value = Array(THROWS).fill(null)
    scores2.value = Array(THROWS).fill(null)
    completedRounds.value = []
    selected.value = null
    viewedRound.value = null
    roundIdBySeq.value = {}
    syncError.value = ''
    tiebreak.value = null
  }

  function resetGame() {
    if (props.matchContext) {
      initEventMatch()
      return
    }
    clearLocalState()
    matchId.value = crypto.randomUUID()
  }

  defineExpose({ resetGame })

  // Rebuild local scoring state from the server when an event match is selected,
  // so previously played rounds can be reviewed and adjusted.
  async function initEventMatch() {
    clearLocalState()
    const ctx = props.matchContext
    if (!ctx) {
      matchId.value = crypto.randomUUID()
      return
    }
    matchId.value = ctx.matchId
    try {
      const rounds = await getRoundsByMatch(ctx.matchId)
      const map = {}
      for (const r of rounds) map[r.sequence] = r.round_id
      roundIdBySeq.value = map
      const throws = await getThrows({ matchId: ctx.matchId })
      restoreFromThrows(throws)
      await ensureRound(currentRound.value)
    } catch (e) {
      syncError.value = 'Could not sync this match with the server.'
    }
  }

  function restoreFromThrows(throws) {
    const ctx = props.matchContext
    const bySeq = {}
    for (const [seq, roundId] of Object.entries(roundIdBySeq.value)) {
      const arr1 = Array(THROWS).fill(null)
      const arr2 = Array(THROWS).fill(null)
      const roundThrows = throws
        .filter(t => t.round_id === roundId)
        .sort((a, b) => (a.timestamp < b.timestamp ? -1 : 1))
      for (const t of roundThrows) {
        const arr = t.player_id === ctx.player1Id ? arr1 : t.player_id === ctx.player2Id ? arr2 : null
        if (!arr) continue
        const idx = arr.indexOf(null)
        if (idx !== -1) arr[idx] = { value: t.points, drop: !!t.is_drop, throwId: t.throw_id }
      }
      bySeq[Number(seq)] = { arr1, arr2 }
    }

    const completed = []
    let cur = 1
    let curScores = null
    for (let seq = 1; seq <= props.totalRounds; seq++) {
      const entry = bySeq[seq]
      const complete = entry && !entry.arr1.includes(null) && !entry.arr2.includes(null)
      if (complete && seq < props.totalRounds) {
        completed.push({ scores1: entry.arr1, scores2: entry.arr2 })
        continue
      }
      cur = seq
      curScores = entry ?? null
      break
    }
    completedRounds.value = completed
    currentRound.value = cur
    scores1.value = curScores ? curScores.arr1 : Array(THROWS).fill(null)
    scores2.value = curScores ? curScores.arr2 : Array(THROWS).fill(null)
  }

  watch(() => props.matchContext, () => { resetGame() }, { immediate: true })

  // Leave a finished match after editing its scores — the API recomputes the
  // winner on every edit, so there is nothing to re-finish.
  async function backToEvent() {
    try { await unlockMatch(matchId.value) } catch (e) { /* lock may already be released */ }
    emit('matchDone')
  }

  async function finishEventMatch() {
    if (tieUnresolved.value) return
    finishing.value = true
    syncError.value = ''
    try {
      await finishMatch(matchId.value)
      try { await unlockMatch(matchId.value) } catch (e) { /* lock may already be released */ }
      emit('matchDone')
    } catch (e) {
      const detail = e?.response?.data?.detail
      syncError.value = typeof detail === 'string' ? detail : (detail?.message ?? 'Failed to finish the match.')
    } finally {
      finishing.value = false
    }
  }

  // Score cell helpers
  function selectScore(player, index) {
    if (showTiebreak.value) return // tie-break throws aren't individually editable
    selected.value = { player, index }
  }

  function deselectScore() {
    selected.value = null
  }

  function confirmReset() {
    resetScore(selected.value.player, selected.value.index)
    selected.value = null
  }

  function isSelected(player, index) {
    return selected.value?.player === player && selected.value?.index === index
  }

  function total(scores) {
    return scores.reduce((s, x) => s + (x ? x.value : 0), 0)
  }

  function scoreAriaLabel(playerName, throwNum, entry) {
    if (!entry) return `${playerName}, throw ${throwNum}, no score yet`
    const clutch = entry.clutch ? ', clutch' : ''
    const drop = entry.drop ? ', drop' : ''
    return `${playerName}, throw ${throwNum}, score ${entry.value}${clutch}${drop}`
  }

  function openTvOverlay() {
    selected.value = null
    viewedRound.value = null
    tvOverlayOpen.value = true
  }

  function closeTvOverlay() {
    tvOverlayOpen.value = false
  }

  watch(tvOverlayOpen, open => {
    document.body.classList.toggle('tv-overlay-active', open)
    emit('tvOverlayChange', open)
  })

  onUnmounted(() => {
    document.body.classList.remove('tv-overlay-active')
  })

  function roundCellLabel(roundNum, playerName, totalScore, status) {
    const score = totalScore !== null ? totalScore : 'not scored'
    const state = status === 'in-progress' ? 'in progress' : status
    return `Round ${roundNum}, ${playerName}, ${score}, ${state}`
  }

  // Keyboard scoring: number keys 0–5 record a regular throw for the left
  // player, or the right player when the left side is locked (its turn is up).
  function handleKeydown(e) {
    if (tvOverlayOpen.value) return
    if (e.metaKey || e.ctrlKey || e.altKey) return
    const el = e.target
    if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) return
    if (!/^[0-5]$/.test(e.key)) return
    const payload = { points: parseInt(e.key), clutch: false }
    if (!leftDisabled.value) applyScoreLeft(payload)
    else if (!rightDisabled.value) applyScoreRight(payload)
    else return
    e.preventDefault()
  }

  onMounted(() => window.addEventListener('keydown', handleKeydown))
  onUnmounted(() => window.removeEventListener('keydown', handleKeydown))
</script>

<template>
  <div class="scoreboard-root">
    <div class="round-bar">
      <span v-if="matchContext" class="event-banner">{{ matchContext.eventName }}</span>
      <span v-if="matchContext?.arenaLabel" class="lane-banner">{{ matchContext.arenaLabel }}</span>
      <div class="round-bar-actions">
        <button
          v-if="!tvOverlayOpen"
          type="button"
          class="display-mode-btn"
          @click="openTvOverlay"
        >
          Show on TV
        </button>
        <p v-if="!tvOverlayOpen" class="display-mode-note">Tap before AirPlay — shows scores only on the TV. Tap Back on the iPad to score again.</p>
      </div>
      <div aria-live="polite" aria-atomic="true" class="status-live-region">
        <span v-if="syncError" class="sync-error" role="alert">{{ syncError }}</span>
      </div>
    </div>

    <div class="tab-bar" role="tablist" aria-label="Scoring panels">
      <button
        type="button"
        role="tab"
        class="tab-btn"
        :class="{ active: activeTab === 'p1' }"
        :aria-selected="activeTab === 'p1'"
        @click="activeTab = 'p1'"
      >{{ leftName }}</button>
      <button
        type="button"
        role="tab"
        class="tab-btn"
        :class="{ active: activeTab === 'scores' }"
        :aria-selected="activeTab === 'scores'"
        @click="activeTab = 'scores'"
      >Scores</button>
      <button
        type="button"
        role="tab"
        class="tab-btn"
        :class="{ active: activeTab === 'p2' }"
        :aria-selected="activeTab === 'p2'"
        @click="activeTab = 'p2'"
      >{{ rightName }}</button>
    </div>

    <div class="app-layout">
      <div class="tab-panel panel-p1" :class="{ active: activeTab === 'p1' }" role="tabpanel">
        <UrbanScore :playerName="leftName" :disabled="leftDisabled" :clutchAvailable="leftClutchAvailable" @score="applyScoreLeft" />
      </div>

      <div class="tab-panel panel-scores" :class="{ active: activeTab === 'scores' }" role="tabpanel" aria-label="Live scores">
      <div class="scoreboard">
        <span class="round-label scoreboard-round">{{ roundTitle }}</span>

        <div class="scoreboard-grid" role="table" aria-label="Current round scores">
          <!-- Player names stay pinned above the (scrollable) score rows -->
          <div class="scoreboard-row scoreboard-head" role="row">
            <div class="col-header" role="columnheader">{{ leftName }}</div>
            <div class="col-header round-col-label" role="columnheader">{{ showTiebreak ? '#' : 'Axe' }}</div>
            <div class="col-header" role="columnheader">{{ rightName }}</div>
          </div>

          <div ref="rowsEl" class="scoreboard-rows" :class="{ 'tiebreak-scroll': showTiebreak }">
            <div class="scoreboard-row" v-for="i in slotCount" :key="i" role="row">
              <!-- Left player cell -->
              <div class="score-cell" :class="{ filled: leftScores[i-1] !== null }" role="cell">
                <template v-if="leftScores[i-1] !== null">
                  <button
                    type="button"
                    class="score-btn"
                    :class="{ selected: isSelected(sidesSwapped ? 2 : 1, i-1) }"
                    :aria-label="scoreAriaLabel(leftName, i, leftScores[i-1])"
                    @click="!isSelected(sidesSwapped ? 2 : 1, i-1) && selectScore(sidesSwapped ? 2 : 1, i-1)"
                  >
                    {{ leftScores[i-1].value }}<sup v-if="leftScores[i-1].drop" class="drop-marker">d</sup>
                  </button>
                  <button
                    v-if="isSelected(sidesSwapped ? 2 : 1, i-1)"
                    type="button"
                    class="reset-cancel-btn"
                    aria-label="Cancel score edit"
                    @click="deselectScore"
                  >✕</button>
                </template>
                <template v-else><span aria-hidden="true">–</span></template>
              </div>

              <div class="round-num" role="cell" :aria-label="`Throw ${i}`">{{ i }}</div>

              <!-- Right player cell -->
              <div class="score-cell" :class="{ filled: rightScores[i-1] !== null }" role="cell">
                <template v-if="rightScores[i-1] !== null">
                  <button
                    type="button"
                    class="score-btn"
                    :class="{ selected: isSelected(sidesSwapped ? 1 : 2, i-1) }"
                    :aria-label="scoreAriaLabel(rightName, i, rightScores[i-1])"
                    @click="isSelected(sidesSwapped ? 1 : 2, i-1) ? confirmReset() : selectScore(sidesSwapped ? 1 : 2, i-1)"
                  >
                    {{ rightScores[i-1].value }}<sup v-if="rightScores[i-1].drop" class="drop-marker">d</sup>
                  </button>
                  <button
                    v-if="isSelected(sidesSwapped ? 1 : 2, i-1)"
                    type="button"
                    class="reset-cancel-btn"
                    aria-label="Cancel score edit"
                    @click="deselectScore"
                  >✕</button>
                </template>
                <template v-else><span aria-hidden="true">–</span></template>
              </div>
            </div>
          </div>

          <!-- Total stays pinned below the score rows -->
          <div class="scoreboard-row scoreboard-total" role="row">
            <div class="total-cell" role="cell">{{ total(leftScores) }}</div>
            <div class="total-label" role="cell">Total</div>
            <div class="total-cell" role="cell">{{ total(rightScores) }}</div>
          </div>
        </div>

        <div class="scoreboard-status-slot" aria-live="polite">
          <button v-if="viewedRound" type="button" class="editing-banner" @click="viewRound(currentRound)">
            Editing Round {{ viewedRound }} — tap to return to Round {{ currentRound }}
          </button>
          <span v-else-if="tiebreakInProgress" class="tiebreak-hint">
            <strong>Sudden death — {{ tiebreak.phase === 'clutch' ? 'Clutch' : 'Bulls' }}.</strong>
            <template v-if="tiebreak.phase === 'bull'"> One throw each; both stick a bull (5) to force clutch.</template>
            <template v-else> Tap Clutch, then score 5, 6, 7 or 0. Three misses each drops back to bulls.</template>
          </span>
          <button v-else-if="needsTiebreak && !tiebreak" type="button" class="next-round-btn" @click="startTiebreak">
            Drawn — Start Tie Breaker
          </button>
          <button v-else-if="roundComplete && !gameOver && !matchContext?.isFinished" type="button" class="next-round-btn" @click="nextRound">
            Round {{ currentRound }} complete — Start Round {{ currentRound + 1 }}
          </button>
          <button v-else-if="gameOver && !matchContext && !tieUnresolved" type="button" class="new-game-btn" @click="emit('requestConfig')">
            {{ gameWinner ? `${gameWinner} wins — New Game` : 'New Game' }}
          </button>
          <span v-else-if="!matchContext?.isFinished && !gameOver && !roundComplete" class="match-in-progress">
            <template v-if="player1Disabled">Waiting for {{ player2Name }}</template>
            <template v-else-if="player2Disabled">Waiting for {{ player1Name }}</template>
            <template v-else>Match in Progress</template>
          </span>
        </div>
      </div>
      </div>

      <div class="tab-panel panel-p2" :class="{ active: activeTab === 'p2' }" role="tabpanel">
        <UrbanScore :playerName="rightName" :mirrored="true" :disabled="rightDisabled" :clutchAvailable="rightClutchAvailable" @score="applyScoreRight" />
      </div>
    </div>

    <div class="results-section">
      <button v-if="matchContext?.isFinished" type="button" class="new-game-btn" @click="backToEvent">
        Done Editing — Back to Event
      </button>
      <button v-else-if="gameOver && matchContext" type="button" class="next-round-btn" :disabled="finishing || tieUnresolved" @click="finishEventMatch">
        {{ finishing ? 'Finishing…' : tieUnresolved ? 'Drawn — settle the tie breaker first' : 'Finish Match' }}
      </button>
      <div class="results-table-wrap">
        <table class="results-table" aria-label="Round by round results">
          <thead>
            <tr>
              <th class="corner" scope="col"></th>
              <th
                v-for="r in allRoundRows"
                :key="r.round"
                scope="col"
                class="round-head"
                :class="{ selectable: r.round <= currentRound, viewing: r.round === displayRound && viewedRound }"
              >
                <button
                  v-if="r.round <= currentRound"
                  type="button"
                  class="round-head-btn"
                  :aria-label="`View round ${r.round}`"
                  @click="viewRound(r.round)"
                >Round {{ r.round }}</button>
                <span v-else>Round {{ r.round }}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th class="player-head" scope="row">{{ player1Name }}</th>
              <td
                v-for="r in allRoundRows"
                :key="r.round"
                :class="{ winner: r.status === 'p1', selectable: r.round <= currentRound, viewing: r.round === displayRound && viewedRound }"
              >
                <button
                  v-if="r.round <= currentRound"
                  type="button"
                  class="round-cell-btn"
                  :aria-label="roundCellLabel(r.round, player1Name, r.t1, r.status)"
                  @click="viewRound(r.round)"
                >{{ r.t1 !== null ? r.t1 : '–' }}</button>
                <span v-else aria-hidden="true">{{ r.t1 !== null ? r.t1 : '–' }}</span>
              </td>
            </tr>
            <tr>
              <th class="player-head" scope="row">{{ player2Name }}</th>
              <td
                v-for="r in allRoundRows"
                :key="r.round"
                :class="{ winner: r.status === 'p2', selectable: r.round <= currentRound, viewing: r.round === displayRound && viewedRound }"
              >
                <button
                  v-if="r.round <= currentRound"
                  type="button"
                  class="round-cell-btn"
                  :aria-label="roundCellLabel(r.round, player2Name, r.t2, r.status)"
                  @click="viewRound(r.round)"
                >{{ r.t2 !== null ? r.t2 : '–' }}</button>
                <span v-else aria-hidden="true">{{ r.t2 !== null ? r.t2 : '–' }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

    </div>
  </div>

  <Teleport to="body">
    <TvScoreOverlay
      v-if="tvOverlayOpen"
      :event-name="matchContext?.eventName"
      :arena-label="matchContext?.arenaLabel"
      :round-title="roundTitle"
      :left-name="leftName"
      :right-name="rightName"
      :player1-name="player1Name"
      :player2-name="player2Name"
      :left-scores="leftScores"
      :right-scores="rightScores"
      :slot-count="slotCount"
      :show-tiebreak="showTiebreak"
      :left-total="total(leftScores)"
      :right-total="total(rightScores)"
      :game-winner="gameWinner"
      :tiebreak-in-progress="tiebreakInProgress"
      :player1-disabled="player1Disabled"
      :player2-disabled="player2Disabled"
      :game-over="gameOver"
      :round-complete="roundComplete"
      :match-finished="!!matchContext?.isFinished"
      :all-round-rows="allRoundRows"
      :current-round="currentRound"
      @close="closeTvOverlay"
    />
  </Teleport>
</template>

<style scoped>
.scoreboard-root {
  --score-scale: 1;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

@media (min-width: 1280px) {
  .scoreboard-root {
    --score-scale: 1.12;
  }
}

@media (min-width: 1920px) {
  .scoreboard-root {
    --score-scale: 1.25;
  }
}

.display-mode-note {
  margin: 0;
  max-width: 360px;
  font-size: 0.8rem;
  line-height: 1.4;
  color: var(--color-muted);
  text-align: center;
}

.round-bar {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.round-bar-actions {
  display: flex;
  justify-content: center;
  width: 100%;
}

.display-mode-btn {
  min-height: var(--touch-min);
  padding: 10px 18px;
  font-size: 0.9rem;
  font-weight: bold;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  color: #c4b5fd;
  background: #1e1b2e;
  border: 1px solid #4c1d95;
  border-radius: 8px;
  cursor: pointer;
}

.display-mode-btn[aria-pressed="true"] {
  color: #fff;
  background: #6d28d9;
  border-color: #8b5cf6;
}

.status-live-region {
  min-height: 0;
}

.round-label {
  font-size: calc(1.2rem * var(--score-scale));
  font-weight: bold;
  letter-spacing: 1px;
  color: #a78bfa;
}

.scoreboard-round {
  margin-bottom: calc(40px * var(--score-scale));
}

/* Fixed-height slot keeps the panel height constant whether the status shows
   the "Match in Progress" text, the editing button, or nothing at all — so the
   score pads don't shift when it changes. */
.scoreboard-status-slot {
  margin-top: 40px;
  margin-bottom: 20px;
  min-height: 76px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.scoreboard-status-slot .match-in-progress {
  padding: 0;
}

.event-banner {
  font-size: 0.8rem;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: #34d399;
}

.lane-banner {
  font-size: 0.85rem;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #60a5fa;
}

.sync-error {
  font-size: 0.85rem;
  font-weight: bold;
  color: #fca5a5;
  background: #3b1212;
  padding: 4px 12px;
  border-radius: 8px;
}

.editing-banner {
  font-size: 0.85rem;
  font-weight: bold;
  color: #fbbf24;
  background: #3b2800;
  border: 1px solid #eab308;
  padding: 6px 14px;
  border-radius: 8px;
  cursor: pointer;
}

.results-table .selectable {
  cursor: pointer;
}

.results-table .selectable:hover {
  background: #1e293b;
}

.results-table .viewing {
  outline: 2px solid #eab308;
  outline-offset: -2px;
}

.app-layout {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 20px;
}

.tab-bar {
  display: none;
}

.tab-btn {
  flex: 1;
  min-height: var(--touch-min);
  padding: 10px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: #94a3b8;
  font-size: 0.85rem;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 1px;
  cursor: pointer;
  margin-bottom: -2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tab-btn.active {
  color: #a78bfa;
  border-bottom-color: #a78bfa;
}

.tab-panel {
  flex: 1;
}

.panel-scores {
  flex: 0 0 min(425px, 100%);
  width: min(425px, 100%);
}

/* iPads are the primary target: portrait iPads (and phones) get the tabbed
   layout; landscape iPads and desktops get the three-column layout. */
@media (max-width: 1023px) {
  .tab-bar {
    display: flex;
    border-bottom: 2px solid #334155;
  }

  .app-layout {
    flex-direction: column;
    align-items: center;
  }

  .tab-panel {
    display: none;
    width: 100%;
    flex: none;
  }

  .tab-panel.active {
    display: flex;
    justify-content: center;
  }

  .panel-scores {
    width: 100%;
    flex-direction: column;
    align-items: center;
  }
}

@media (max-width: 640px) {
  .scoreboard {
    padding: 16px 8px;
  }

  .scoreboard-row {
    gap: 10px;
    grid-template-columns: minmax(0, 1fr) 36px minmax(0, 1fr);
  }

  .results-table .round-head,
  .results-table td {
    padding: 10px 14px;
  }

  .results-table .player-head {
    padding: 10px 12px;
  }
}

.scoreboard {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 16px;
  box-sizing: border-box;
}

.scoreboard-grid {
  display: flex;
  flex-direction: column;
  gap: 5px;
  width: 100%;
}

/* Header, each score line, and the total share one column template so their
   columns line up even though they're separate rows (the score lines scroll
   between the pinned header and total). Fixed middle column keeps the three
   aligned regardless of their differing middle content (Axe / # / Total). */
.scoreboard-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 48px minmax(0, 1fr);
  gap: 20px;
  align-items: center;
  width: 100%;
}

.scoreboard-rows {
  display: flex;
  flex-direction: column;
  gap: 5px;
  width: 100%;
}

/* Tie breaker: cap the scrollable score lines at five rows (5 × 40px + 4 × 5px
   gap) so a sixth-plus sudden-death attempt scrolls without moving the pinned
   header/total or nudging the score pads. */
.scoreboard-rows.tiebreak-scroll {
  max-height: 220px;
  overflow-y: auto;
}

.col-header {
  font-size: calc(1.1rem * var(--score-scale));
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #e2e8f0;
  text-align: center;
  padding-bottom: 4px;
  border-bottom: 1px solid #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.round-col-label {
  color: #94a3b8;
  font-size: calc(1.1rem * var(--score-scale));
}

.score-cell {
  text-align: center;
  font-size: calc(1.4rem * var(--score-scale));
  font-weight: bold;
  color: #64748b;
  padding: 4px 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-height: calc(48px * var(--score-scale));
}

.score-cell.filled {
  color: #e2e8f0;
}

.score-btn {
  font-size: calc(1.4rem * var(--score-scale));
  font-weight: bold;
  color: #e2e8f0;
  background: none;
  border: none;
  cursor: pointer;
  padding: 6px 10px;
  min-width: calc(44px * var(--score-scale));
  min-height: calc(44px * var(--score-scale));
  border-radius: 4px;
  line-height: 1;
}

.score-btn:hover {
  background: #1e293b;
}

.score-btn.selected {
  background: #3b2800;
  outline: 2px solid #eab308;
  border-radius: 4px;
}

.score-btn.selected:hover {
  background: #4d3500;
}

.reset-cancel-btn {
  font-size: 0.85rem;
  font-weight: bold;
  color: #e2e8f0;
  background: #334155;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  width: 32px;
  height: 32px;
  min-width: 32px;
  min-height: 32px;
  padding: 0;
  line-height: 1;
  text-align: center;
  align-self: center;
  flex-shrink: 0;
}

.reset-cancel-btn:hover {
  background: #475569;
}

.drop-marker {
  font-size: 0.55rem;
  font-weight: bold;
  vertical-align: super;
}

.round-num {
  text-align: center;
  font-size: calc(0.85rem * var(--score-scale));
  color: #94a3b8;
}

.total-cell {
  text-align: center;
  font-size: calc(1.6rem * var(--score-scale));
  font-weight: bold;
  color: #e2e8f0;
  padding-top: 6px;
  margin-top: 4px;
}

.total-label {
  text-align: center;
  font-size: calc(0.85rem * var(--score-scale));
  font-weight: bold;
  text-transform: uppercase;
  color: #8b5cf6;
  border-top: 2px solid #8b5cf6;
  padding-top: 6px;
  margin-top: 4px;
}

.next-round-btn {
  padding: 12px 28px;
  min-height: var(--touch-min);
  font-size: calc(1rem * var(--score-scale));
  font-weight: bold;
  background-color: #059669;
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.next-round-btn:hover {
  background-color: #047857;
}

.match-in-progress {
  display: inline-block;
  padding: 12px 28px;
  font-size: calc(1rem * var(--score-scale));
  font-weight: bold;
  color: #94a3b8;
  letter-spacing: 1px;
}

.results-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}

.results-title {
  font-size: 1.1rem;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: #a78bfa;
  margin: 0;
}

.results-table-wrap {
  max-width: 100%;
  overflow-x: auto;
}

.results-table {
  border-collapse: collapse;
  font-size: calc(1.15rem * var(--score-scale));
}

.round-head-btn,
.round-cell-btn {
  width: 100%;
  min-height: var(--touch-min);
  padding: 8px 12px;
  font: inherit;
  color: inherit;
  background: transparent;
  border: none;
  cursor: pointer;
  border-radius: 4px;
}

.round-head-btn {
  color: #a78bfa;
  font-size: calc(1.1rem * var(--score-scale));
  font-weight: bold;
}

.round-head-btn:hover,
.round-cell-btn:hover {
  background: #1e293b;
}

.results-table .selectable .round-cell-btn {
  cursor: pointer;
}

/* Round-number column headers across the top */
.results-table .round-head {
  padding: 8px 10px;
  text-align: center;
  border-bottom: 2px solid #8b5cf6;
  font-size: calc(1.1rem * var(--score-scale));
  color: #a78bfa;
  white-space: nowrap;
}

/* Player-name row headers down the left */
.results-table .player-head {
  padding: 12px 22px;
  text-align: left;
  font-size: 0.98rem;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #e2e8f0;
  white-space: nowrap;
}

.results-table .corner {
  border-bottom: 2px solid #8b5cf6;
}

.results-table td {
  padding: 8px 10px;
  text-align: center;
  border-bottom: 1px solid #1e293b;
  color: #cbd5e1;
}

.results-table td.winner {
  font-weight: bold;
  color: #6ee7b7;
  background: #064e3b;
}

.overall-winner {
  font-size: 1.6rem;
  font-weight: bold;
  color: #34d399;
  letter-spacing: 2px;
  text-transform: uppercase;
  padding: 12px 24px;
  border: 3px solid #059669;
  border-radius: 12px;
  background: #022c22;
}

.tiebreak-hint {
  margin: 0;
  max-width: 340px;
  font-size: 0.85rem;
  color: #fbbf24;
  text-align: center;
}

.new-game-btn {
  font-size: calc(0.95rem * var(--score-scale));
  font-weight: bold;
  letter-spacing: 1px;
  text-transform: uppercase;
  padding: 10px 20px;
  min-height: var(--touch-min);
  background: #7c3aed;
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}

.new-game-btn:hover {
  background: #6d28d9;
}
</style>
