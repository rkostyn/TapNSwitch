<script setup>
  import { ref, computed, watch } from 'vue'
  import UrbanScore from './UrbanScore.vue'
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
  const emit = defineEmits(['resetScore', 'select', 'deselect', 'requestConfig', 'matchDone'])

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

  const displayRound = computed(() => viewedRound.value ?? currentRound.value)
  const displayScores1 = computed(() =>
    viewedRound.value ? completedRounds.value[viewedRound.value - 1].scores1 : scores1.value
  )
  const displayScores2 = computed(() =>
    viewedRound.value ? completedRounds.value[viewedRound.value - 1].scores2 : scores2.value
  )

  // Sides swap every round; derive from the round on display
  const sidesSwapped = computed(() => (displayRound.value - 1) % 2 === 1)

  // Which player name/scores are on the left vs right panel for the displayed round
  const leftName = computed(() => sidesSwapped.value ? props.player2Name : props.player1Name)
  const rightName = computed(() => sidesSwapped.value ? props.player1Name : props.player2Name)
  const leftScores = computed(() => sidesSwapped.value ? displayScores2.value : displayScores1.value)
  const rightScores = computed(() => sidesSwapped.value ? displayScores1.value : displayScores2.value)
  const applyScoreLeft = (value) => routeScore(sidesSwapped.value ? 2 : 1, value)
  const applyScoreRight = (value) => routeScore(sidesSwapped.value ? 1 : 2, value)

  // The score panels do double duty: during a tie breaker they record the
  // sudden-death throws; otherwise they score the round on display
  function routeScore(player, value) {
    if (tiebreakActive.value && !viewedRound.value && !selected.value) tiebreakScore(player, value)
    else applyScore(player, value)
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
  // During a tie breaker a side locks once its single throw is recorded.
  const tbEntered = (player) => (player === 1 ? tiebreak.value?.s1 : tiebreak.value?.s2) !== null

  function sideDisabled(player) {
    if (player === ghostSide.value) return true // the ghost never throws by hand
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

  // A tied game cannot be finished until the tie breaker settles it
  const tieUnresolved = computed(() =>
    gameOver.value && overallWinner.value === 'tie' && !tiebreak.value?.winner
  )

  function tiebreakSeq() {
    return props.totalRounds + tiebreak.value.attempt
  }

  function startTiebreak() {
    tiebreak.value = { phase: 'bull', attempt: 1, s1: null, s2: null, missedClutchRounds: 0, winner: null }
    ensureRound(tiebreakSeq()).catch(() => { syncError.value = 'Could not start the tie-breaker round on the server.' })
  }

  function tiebreakScore(player, value) {
    const tb = tiebreak.value
    if (!tb || tb.winner) return
    if ((player === 1 ? tb.s1 : tb.s2) !== null) return
    const drop = value === 'Drop'
    const entry = { value: drop ? 0 : parseInt(value), drop }
    if (player === 1) tb.s1 = entry
    else tb.s2 = entry
    syncEntry(entry, player, null, tiebreakSeq())
    if (tb.s1 !== null && tb.s2 !== null) resolveTiebreakAttempt()
  }

  function resolveTiebreakAttempt() {
    const tb = tiebreak.value
    const v1 = tb.s1.value, v2 = tb.s2.value
    if (v1 !== v2) {
      tb.winner = v1 > v2 ? props.player1Name : props.player2Name
      return
    }
    if (tb.phase === 'bull') {
      // Both stuck their bulls — they may go up for clutch
      if (v1 === 5) tb.phase = 'clutch'
    } else if (v1 === 7) {
      // Both hit clutch — stay up for clutch
      tb.missedClutchRounds = 0
    } else {
      tb.missedClutchRounds++
      if (tb.missedClutchRounds >= 3) {
        tb.phase = 'bull'
        tb.missedClutchRounds = 0
      }
    }
    tb.attempt++
    tb.s1 = null
    tb.s2 = null
    ensureRound(tiebreakSeq()).catch(() => { syncError.value = 'Could not start the tie-breaker round on the server.' })
  }

  function applyScore(player, value) {
    const entry = value === 'Drop'
      ? { value: 0, drop: true }
      : (() => { const num = parseInt(value); return isNaN(num) ? null : { value: num, drop: false } })()
    if (!entry) return

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
    const entry = { value: 0, drop: false }
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
        isDrop: entry.drop,
        clutchCalled: entry.value === 7,
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
</script>

<template>
  <div class="scoreboard-root">
    <div class="round-bar">
      <span v-if="matchContext" class="event-banner">{{ matchContext.eventName }}</span>
      <span v-if="matchContext?.arenaLabel" class="arena-banner">{{ matchContext.arenaLabel }}</span>
      <span class="round-label">Round {{ displayRound }} of {{ totalRounds }}</span>
      <button v-if="viewedRound" class="editing-banner" @click="viewRound(currentRound)">
        Editing Round {{ viewedRound }} — tap to return to Round {{ currentRound }}
      </button>
      <span v-if="syncError" class="sync-error">{{ syncError }}</span>
    </div>

    <div class="tab-bar">
      <button class="tab-btn" :class="{ active: activeTab === 'p1' }" @click="activeTab = 'p1'">{{ leftName }}</button>
      <button class="tab-btn" :class="{ active: activeTab === 'scores' }" @click="activeTab = 'scores'">Scores</button>
      <button class="tab-btn" :class="{ active: activeTab === 'p2' }" @click="activeTab = 'p2'">{{ rightName }}</button>
    </div>

    <div class="app-layout">
      <div class="tab-panel panel-p1" :class="{ active: activeTab === 'p1' }">
        <UrbanScore :playerName="leftName" :disabled="leftDisabled" :clutchAvailable="leftClutchAvailable" @score="applyScoreLeft" />
      </div>

      <div class="tab-panel panel-scores" :class="{ active: activeTab === 'scores' }">
      <div class="scoreboard">
        <h2 class="scoreboard-title">Scores</h2>

        <div class="scoreboard-grid">
          <div class="col-header">{{ leftName }}</div>
          <div class="col-header round-col-label">Axe</div>
          <div class="col-header">{{ rightName }}</div>

          <template v-for="i in THROWS" :key="i">
            <!-- Left player cell -->
            <div class="score-cell" :class="{ filled: leftScores[i-1] !== null }">
              <template v-if="leftScores[i-1] !== null">
                <button class="score-btn" :class="{ selected: isSelected(sidesSwapped ? 2 : 1, i-1) }"
                  @click="!isSelected(sidesSwapped ? 2 : 1, i-1) && selectScore(sidesSwapped ? 2 : 1, i-1)">
                  {{ leftScores[i-1].value }}<sup v-if="leftScores[i-1].drop" class="drop-marker">d</sup>
                </button>
                <button v-if="isSelected(sidesSwapped ? 2 : 1, i-1)" class="reset-cancel-btn" @click="deselectScore">✕</button>
              </template>
              <template v-else>–</template>
            </div>

            <div class="round-num">{{ i }}</div>

            <!-- Right player cell -->
            <div class="score-cell" :class="{ filled: rightScores[i-1] !== null }">
              <template v-if="rightScores[i-1] !== null">
                <button class="score-btn" :class="{ selected: isSelected(sidesSwapped ? 1 : 2, i-1) }"
                  @click="isSelected(sidesSwapped ? 1 : 2, i-1) ? confirmReset() : selectScore(sidesSwapped ? 1 : 2, i-1)">
                  {{ rightScores[i-1].value }}<sup v-if="rightScores[i-1].drop" class="drop-marker">d</sup>
                </button>
                <button v-if="isSelected(sidesSwapped ? 1 : 2, i-1)" class="reset-cancel-btn" @click="deselectScore">✕</button>
              </template>
              <template v-else>–</template>
            </div>
          </template>

          <div class="total-cell">{{ total(leftScores) }}</div>
          <div class="total-label">Total</div>
          <div class="total-cell">{{ total(rightScores) }}</div>
        </div>
      </div>
      </div>

      <div class="tab-panel panel-p2" :class="{ active: activeTab === 'p2' }">
        <UrbanScore :playerName="rightName" :mirrored="true" :disabled="rightDisabled" :clutchAvailable="rightClutchAvailable" @score="applyScoreRight" />
      </div>
    </div>

    <div class="results-section">
      <button v-if="matchContext?.isFinished" class="new-game-btn" @click="backToEvent">
        Done Editing — Back to Event
      </button>
      <button v-else-if="gameOver && matchContext" class="next-round-btn" :disabled="finishing || tieUnresolved" @click="finishEventMatch">
        {{ finishing ? 'Finishing…' : tieUnresolved ? 'Drawn — settle the tie breaker first' : 'Finish Match' }}
      </button>
      <button v-else-if="gameOver" class="new-game-btn" @click="emit('requestConfig')">New Game</button>
      <button v-else-if="roundComplete" class="next-round-btn" @click="nextRound">
        Round {{ currentRound }} complete — Start Round {{ currentRound + 1 }}
      </button>
      <span v-else class="match-in-progress">
        <template v-if="player1Disabled">Waiting for {{ player2Name }}</template>
        <template v-else-if="player2Disabled">Waiting for {{ player1Name }}</template>
        <template v-else>Match in Progress</template>
      </span>
      <h3 class="results-title">Results</h3>
      <table class="results-table">
        <thead>
          <tr>
            <th>Round</th>
            <th>{{ player1Name }}</th>
            <th>{{ player2Name }}</th>
            <th>Winner</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in allRoundRows"
            :key="r.round"
            :class="{ selectable: r.round <= currentRound, viewing: r.round === displayRound && viewedRound }"
            @click="viewRound(r.round)"
          >
            <td>{{ r.round }}</td>
            <td :class="{ winner: r.status === 'p1' }">{{ r.t1 !== null ? r.t1 : '–' }}</td>
            <td :class="{ winner: r.status === 'p2' }">{{ r.t2 !== null ? r.t2 : '–' }}</td>
            <td>
              <span v-if="r.status === 'p1'" class="win-badge p1">{{ player1Name }}</span>
              <span v-else-if="r.status === 'p2'" class="win-badge p2">{{ player2Name }}</span>
              <span v-else-if="r.status === 'tie'" class="win-badge tie">Tie</span>
              <span v-else-if="r.status === 'in-progress'" class="win-badge in-progress">In Progress</span>
              <span v-else class="win-badge pending">–</span>
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="gameOver && !tiebreak" class="overall-winner" :class="{ draw: overallWinner === 'tie' }">
        <span v-if="overallWinner === 'tie'">It's a draw!</span>
        <span v-else>{{ overallWinner }} wins the game!</span>
      </div>

      <button v-if="needsTiebreak && !tiebreak" class="next-round-btn" @click="startTiebreak">
        Start Tie Breaker
      </button>

      <div v-if="tiebreak" class="tiebreak-box">
        <template v-if="!tiebreak.winner">
          <h3 class="results-title">
            Tie Breaker — {{ tiebreak.phase === 'clutch' ? 'Clutch' : 'Bulls' }} · Throw {{ tiebreak.attempt }}
          </h3>
          <p class="tiebreak-hint">
            <template v-if="tiebreak.phase === 'bull'">One throw each, scored with the regular buttons. If both stick a bull (5), they go up for clutch.</template>
            <template v-else>One throw each — call clutch on the regular buttons. Three misses in a row sends it back down to bulls.</template>
          </p>
          <div class="tiebreak-grid">
            <div class="tiebreak-side" v-for="player in [1, 2]" :key="player">
              <span class="tiebreak-name">{{ player === 1 ? player1Name : player2Name }}</span>
              <span v-if="(player === 1 ? tiebreak.s1 : tiebreak.s2) !== null" class="tiebreak-score">
                {{ (player === 1 ? tiebreak.s1 : tiebreak.s2).value }}<sup v-if="(player === 1 ? tiebreak.s1 : tiebreak.s2).drop" class="drop-marker">d</sup>
              </span>
              <span v-else class="tiebreak-waiting">waiting…</span>
            </div>
          </div>
        </template>
        <div v-else class="overall-winner">{{ tiebreak.winner }} wins the tie breaker!</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.scoreboard-root {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.round-bar {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.round-label {
  font-size: 1.2rem;
  font-weight: bold;
  letter-spacing: 1px;
  color: #a78bfa;
}

.event-banner {
  font-size: 0.8rem;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: #34d399;
}

.arena-banner {
  font-size: 0.75rem;
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

.results-table tr.selectable {
  cursor: pointer;
}

.results-table tr.selectable:hover td {
  background: #1e293b;
}

.results-table tr.viewing td {
  background: #3b2800;
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
  padding: 10px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: #64748b;
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
  flex: 0 0 500px;
  width: 500px;
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

.scoreboard {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 16px;
  box-sizing: border-box;
}

.scoreboard-title {
  font-size: 1.1rem;
  font-weight: bold;
  margin: 0 0 16px;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: #a78bfa;
}

.scoreboard-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  gap: 6px 24px;
  align-items: center;
  width: 100%;
}

.col-header {
  font-size: 1.1rem;
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
  color: #475569;
  font-size: 1.1rem;
}

.score-cell {
  text-align: center;
  font-size: 1.4rem;
  font-weight: bold;
  color: #334155;
  padding: 4px 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 40px;
}

.score-cell.filled {
  color: #e2e8f0;
}

.score-btn {
  font-size: 1.4rem;
  font-weight: bold;
  color: #e2e8f0;
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px 6px;
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
  font-size: 0.75rem;
  font-weight: bold;
  color: #e2e8f0;
  background: #334155;
  border: none;
  border-radius: 50%;
  cursor: pointer;
  width: 16px;
  height: 16px;
  padding: 0;
  line-height: 16px;
  text-align: center;
  align-self: flex-start;
  margin-top: 2px;
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
  font-size: 0.75rem;
  color: #475569;
}

.total-cell {
  text-align: center;
  font-size: 1.6rem;
  font-weight: bold;
  color: #e2e8f0;
  padding-top: 6px;
  margin-top: 4px;
}

.total-label {
  text-align: center;
  font-size: 0.75rem;
  font-weight: bold;
  text-transform: uppercase;
  color: #8b5cf6;
  border-top: 2px solid #8b5cf6;
  padding-top: 6px;
  margin-top: 4px;
}

.next-round-btn {
  padding: 12px 28px;
  font-size: 1rem;
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
  font-size: 1rem;
  font-weight: bold;
  color: #475569;
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

.results-table {
  border-collapse: collapse;
  min-width: 320px;
  font-size: 1rem;
}

.results-table th {
  padding: 8px 20px;
  text-align: center;
  border-bottom: 2px solid #8b5cf6;
  text-transform: uppercase;
  font-size: 0.8rem;
  letter-spacing: 1px;
  color: #a78bfa;
}

.results-table td {
  padding: 8px 20px;
  text-align: center;
  border-bottom: 1px solid #1e293b;
  color: #cbd5e1;
}

.results-table td.winner {
  font-weight: bold;
  color: #34d399;
}

.win-badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: bold;
}

.win-badge.p1 { background: #1e3a5f; color: #93c5fd; }
.win-badge.p2 { background: #3b1212; color: #fca5a5; }
.win-badge.tie { background: #1e293b; color: #94a3b8; }
.win-badge.in-progress { background: #3b2800; color: #fbbf24; }
.win-badge.pending { background: none; color: #334155; }

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

.overall-winner.draw {
  color: #fbbf24;
  border-color: #b45309;
  background: #3b2800;
}

.tiebreak-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border: 2px solid #eab308;
  border-radius: 12px;
  background: #1c1503;
  width: 100%;
  max-width: 520px;
  box-sizing: border-box;
}

.tiebreak-hint {
  margin: 0;
  font-size: 0.85rem;
  color: #fbbf24;
  text-align: center;
}

.tiebreak-grid {
  display: flex;
  gap: 24px;
  width: 100%;
  justify-content: center;
}

.tiebreak-side {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.tiebreak-name {
  font-weight: bold;
  color: #e2e8f0;
  text-transform: uppercase;
  font-size: 0.85rem;
  letter-spacing: 1px;
}

.tiebreak-score {
  font-size: 2rem;
  font-weight: bold;
  color: #34d399;
}

.tiebreak-waiting {
  font-size: 1rem;
  color: #64748b;
  font-style: italic;
}

.new-game-btn {
  font-size: 0.95rem;
  font-weight: bold;
  letter-spacing: 1px;
  text-transform: uppercase;
  padding: 8px 20px;
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
