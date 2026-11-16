<script setup lang="ts">
  import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
  import UrbanScore from './UrbanScore.vue'
  import { arenaLabel } from '../venue'
  import type { MatchContext } from '../match'
  import { roundTotal, type PlayerSide, type ScorePayload } from '../scoring/rules'
  import { useMatchSync } from '../composables/useMatchSync'
  import { useMatchScoring } from '../composables/useMatchScoring'

  const props = defineProps<{
    player1Name: string
    player2Name: string
    totalRounds: number
    matchContext: MatchContext | null
  }>()
  const emit = defineEmits<{
    requestConfig: []
    matchDone: []
  }>()

  const sync = useMatchSync(() => props.matchContext)
  const { syncError, finishing } = sync
  const {
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
    score,
    startTiebreak,
    nextRound,
    viewRound,
    selectScore,
    confirmReset,
    isSelected,
    reset,
  } = useMatchScoring(props, sync)

  // Narrow layouts show one panel at a time
  const activeTab = ref<'p1' | 'scores' | 'p2'>('p1')

  // Scroll container for the score lines — kept pinned to the bottom as tie-break
  // attempts pile up past the visible five slots
  const rowsEl = ref<HTMLElement | null>(null)

  // As sudden death adds slots, keep the newest attempt in view at the bottom
  watch(slotCount, () => {
    if (!showTiebreak.value) return
    nextTick(() => {
      if (rowsEl.value) rowsEl.value.scrollTop = rowsEl.value.scrollHeight
    })
  })

  // Which player name/scores/pad state is on the left vs right panel for the displayed round
  const leftPlayer = computed<PlayerSide>(() => (sidesSwapped.value ? 2 : 1))
  const rightPlayer = computed<PlayerSide>(() => (sidesSwapped.value ? 1 : 2))
  const leftName = computed(() => sidesSwapped.value ? props.player2Name : props.player1Name)
  const rightName = computed(() => sidesSwapped.value ? props.player1Name : props.player2Name)
  const leftScores = computed(() => sidesSwapped.value ? displayScores2.value : displayScores1.value)
  const rightScores = computed(() => sidesSwapped.value ? displayScores1.value : displayScores2.value)
  const leftDisabled = computed(() => padDisabled(leftPlayer.value))
  const rightDisabled = computed(() => padDisabled(rightPlayer.value))
  const leftClutchAvailable = computed(() => clutchAvailable(leftPlayer.value))
  const rightClutchAvailable = computed(() => clutchAvailable(rightPlayer.value))
  const applyScoreLeft = (payload: ScorePayload) => score(leftPlayer.value, payload)
  const applyScoreRight = (payload: ScorePayload) => score(rightPlayer.value, payload)

  const total = roundTotal

  function resetGame() {
    void reset()
  }

  defineExpose({ resetGame })

  // Rebuild local scoring state (from the server, for an event match) whenever
  // a match is selected, so previously played rounds can be reviewed and adjusted.
  watch(() => props.matchContext, () => { resetGame() }, { immediate: true })

  async function backToEvent() {
    await sync.leave()
    emit('matchDone')
  }

  async function finishEventMatch() {
    if (tieUnresolved.value) return
    if (await sync.finish()) emit('matchDone')
  }

  // Keyboard scoring: number keys 0, 1, 3 and 5 record a regular throw for the left
  // player, or the right player when the left side is locked (its turn is up).
  function handleKeydown(e: KeyboardEvent) {
    if (e.metaKey || e.ctrlKey || e.altKey) return
    const el = e.target as HTMLElement | null
    if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) return
    if (!/^[0135]$/.test(e.key)) return
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
      <span v-if="matchContext" class="event-banner">
        {{ matchContext.eventName }}
        <span v-if="matchContext.arenaIds?.length" class="event-arenas">{{ arenaLabel(matchContext.arenaIds) }}</span>
      </span>
      <span v-if="matchContext?.arenaLabel" class="lane-banner">{{ matchContext.arenaLabel }}</span>
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
        <span class="round-label scoreboard-round">
          {{ showTiebreak ? 'Tie Breaker' : `Round ${displayRound} of ${totalRounds}` }}
        </span>

        <div class="scoreboard-grid">
          <!-- Player names stay pinned above the (scrollable) score rows -->
          <div class="scoreboard-row scoreboard-head">
            <div class="col-header">{{ leftName }}</div>
            <div class="col-header round-col-label">{{ showTiebreak ? '#' : 'Axe' }}</div>
            <div class="col-header">{{ rightName }}</div>
          </div>

          <div ref="rowsEl" class="scoreboard-rows" :class="{ 'tiebreak-scroll': showTiebreak }">
            <div class="scoreboard-row" v-for="i in slotCount" :key="i">
              <!-- Left player cell -->
              <div class="score-cell" :class="{ filled: leftScores[i-1] !== null }">
                <template v-if="leftScores[i-1] !== null">
                  <button
                    type="button"
                    class="score-btn"
                    :class="{ selected: isSelected(sidesSwapped ? 2 : 1, i-1) }"
                    @click="isSelected(sidesSwapped ? 2 : 1, i-1) ? confirmReset() : selectScore(sidesSwapped ? 2 : 1, i-1)"
                  >
                    {{ leftScores[i-1]?.value }}<sup v-if="leftScores[i-1]?.drop" class="drop-marker">d</sup>
                  </button>
                  <button
                    v-if="isSelected(sidesSwapped ? 2 : 1, i-1)"
                    type="button"
                    class="reset-cancel-btn"
                    aria-label="Delete score"
                    @click.stop="confirmReset"
                  >✕</button>
                </template>
                <template v-else>–</template>
              </div>

              <div class="round-num">{{ i }}</div>

              <!-- Right player cell -->
              <div class="score-cell" :class="{ filled: rightScores[i-1] !== null }">
                <template v-if="rightScores[i-1] !== null">
                  <button
                    type="button"
                    class="score-btn"
                    :class="{ selected: isSelected(sidesSwapped ? 1 : 2, i-1) }"
                    @click="isSelected(sidesSwapped ? 1 : 2, i-1) ? confirmReset() : selectScore(sidesSwapped ? 1 : 2, i-1)"
                  >
                    {{ rightScores[i-1]?.value }}<sup v-if="rightScores[i-1]?.drop" class="drop-marker">d</sup>
                  </button>
                  <button
                    v-if="isSelected(sidesSwapped ? 1 : 2, i-1)"
                    type="button"
                    class="reset-cancel-btn"
                    aria-label="Delete score"
                    @click.stop="confirmReset"
                  >✕</button>
                </template>
                <template v-else>–</template>
              </div>
            </div>
          </div>

          <!-- Total stays pinned below the score rows -->
          <div class="scoreboard-row scoreboard-total">
            <div class="total-cell">{{ total(leftScores) }}</div>
            <div class="total-label">Total</div>
            <div class="total-cell">{{ total(rightScores) }}</div>
          </div>
        </div>

        <div class="scoreboard-status-slot">
          <button v-if="viewedRound" class="editing-banner" @click="viewRound(currentRound)">
            Editing Round {{ viewedRound }} — tap to return to Round {{ currentRound }}
          </button>
          <span v-else-if="tiebreakInProgress" class="tiebreak-hint">
            <strong>Sudden death — {{ tiebreak?.phase === 'clutch' ? 'Clutch' : 'Bulls' }}.</strong>
            <template v-if="tiebreak?.phase === 'bull'"> One throw each; both stick a bull (5) to force clutch.</template>
            <template v-else> Tap Clutch, then score 7 or 0. Three misses each drops back to bulls.</template>
          </span>
          <button v-else-if="needsTiebreak && !tiebreak" class="next-round-btn" @click="startTiebreak">
            Drawn — Start Tie Breaker
          </button>
          <button v-else-if="roundComplete && !gameOver && !matchContext?.isFinished" class="next-round-btn" @click="nextRound">
            Round {{ currentRound }} complete — Start Round {{ currentRound + 1 }}
          </button>
          <button v-else-if="gameOver && !matchContext && !tieUnresolved" class="new-game-btn" @click="emit('requestConfig')">
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
      <div class="results-table-wrap">
        <table class="results-table">
          <thead>
            <tr>
              <th class="corner"></th>
              <th
                v-for="r in allRoundRows"
                :key="r.round"
                class="round-head"
                :class="{ selectable: r.round <= currentRound, viewing: r.round === displayRound && viewedRound }"
                @click="viewRound(r.round)"
              >Round {{ r.round }}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th class="player-head">{{ player1Name }}</th>
              <td
                v-for="r in allRoundRows"
                :key="r.round"
                :class="{ winner: r.status === 'p1', selectable: r.round <= currentRound, viewing: r.round === displayRound && viewedRound }"
                @click="viewRound(r.round)"
              >{{ r.t1 !== null ? r.t1 : '–' }}</td>
            </tr>
            <tr>
              <th class="player-head">{{ player2Name }}</th>
              <td
                v-for="r in allRoundRows"
                :key="r.round"
                :class="{ winner: r.status === 'p2', selectable: r.round <= currentRound, viewing: r.round === displayRound && viewedRound }"
                @click="viewRound(r.round)"
              >{{ r.t2 !== null ? r.t2 : '–' }}</td>
            </tr>
          </tbody>
        </table>
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

.scoreboard-round {
  margin-bottom: 40px;
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

.event-arenas {
  margin-left: 8px;
  color: #fbbf24;
  letter-spacing: 1px;
}

.lane-banner {
  font-size: 0.8rem;
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
  flex: 0 0 425px;
  width: 425px;
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

.results-table-wrap {
  max-width: 100%;
  overflow-x: auto;
}

.results-table {
  border-collapse: collapse;
  font-size: 1.15rem;
}

/* Round-number column headers across the top */
.results-table .round-head {
  padding: 12px 42px;
  text-align: center;
  border-bottom: 2px solid #8b5cf6;
  font-size: 1.25rem;
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
  padding: 12px 32px;
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
