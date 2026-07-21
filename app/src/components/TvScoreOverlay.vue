<script setup>
  defineProps({
    eventName: String,
    arenaLabel: String,
    roundTitle: String,
    leftName: String,
    rightName: String,
    player1Name: String,
    player2Name: String,
    leftScores: Array,
    rightScores: Array,
    slotCount: Number,
    showTiebreak: Boolean,
    leftTotal: Number,
    rightTotal: Number,
    gameWinner: String,
    tiebreakInProgress: Boolean,
    player1Disabled: Boolean,
    player2Disabled: Boolean,
    gameOver: Boolean,
    roundComplete: Boolean,
    matchFinished: Boolean,
    allRoundRows: Array,
    currentRound: Number,
  })

  const emit = defineEmits(['close'])
</script>

<template>
  <div class="tv-overlay" role="dialog" aria-label="TV score display">
    <button type="button" class="coach-return-btn" aria-label="Back to iPad scoring" @click="emit('close')">
      Back to Scoring
    </button>

    <div class="tv-content">
      <header class="tv-header">
        <span v-if="eventName" class="event-banner">{{ eventName }}</span>
        <span v-if="arenaLabel" class="lane-banner">{{ arenaLabel }}</span>
        <span class="round-label">{{ roundTitle }}</span>
      </header>

      <div class="scoreboard-grid" aria-label="Current round scores">
        <div class="scoreboard-row scoreboard-head">
          <div class="col-header">{{ leftName }}</div>
          <div class="col-header round-col-label">{{ showTiebreak ? '#' : 'Axe' }}</div>
          <div class="col-header">{{ rightName }}</div>
        </div>

        <div class="scoreboard-rows" :class="{ 'tiebreak-scroll': showTiebreak }">
          <div class="scoreboard-row" v-for="i in slotCount" :key="i">
            <div class="score-cell" :class="{ filled: leftScores[i - 1] !== null }">
              <span v-if="leftScores[i - 1] !== null" class="score-readout">
                {{ leftScores[i - 1].value }}<sup v-if="leftScores[i - 1].drop" class="drop-marker">d</sup>
              </span>
              <span v-else class="score-empty" aria-hidden="true">–</span>
            </div>
            <div class="round-num">{{ i }}</div>
            <div class="score-cell" :class="{ filled: rightScores[i - 1] !== null }">
              <span v-if="rightScores[i - 1] !== null" class="score-readout">
                {{ rightScores[i - 1].value }}<sup v-if="rightScores[i - 1].drop" class="drop-marker">d</sup>
              </span>
              <span v-else class="score-empty" aria-hidden="true">–</span>
            </div>
          </div>
        </div>

        <div class="scoreboard-row scoreboard-total">
          <div class="total-cell">{{ leftTotal }}</div>
          <div class="total-label">Total</div>
          <div class="total-cell">{{ rightTotal }}</div>
        </div>
      </div>

      <div class="status-slot" aria-live="polite">
        <span v-if="gameWinner" class="spectator-winner">{{ gameWinner }} wins</span>
        <span v-else-if="tiebreakInProgress" class="spectator-status">Tie breaker</span>
        <span v-else-if="!matchFinished && !gameOver && !roundComplete" class="spectator-status">
          <template v-if="player1Disabled">Waiting for {{ player2Name }}</template>
          <template v-else-if="player2Disabled">Waiting for {{ player1Name }}</template>
          <template v-else>Match in progress</template>
        </span>
      </div>

      <div class="results-table-wrap">
        <table class="results-table" aria-label="Round by round results">
          <thead>
            <tr>
              <th class="corner" scope="col"></th>
              <th v-for="r in allRoundRows" :key="r.round" scope="col" class="round-head">Round {{ r.round }}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th class="player-head" scope="row">{{ player1Name }}</th>
              <td v-for="r in allRoundRows" :key="r.round" :class="{ winner: r.status === 'p1' }">
                {{ r.t1 !== null ? r.t1 : '–' }}
              </td>
            </tr>
            <tr>
              <th class="player-head" scope="row">{{ player2Name }}</th>
              <td v-for="r in allRoundRows" :key="r.round" :class="{ winner: r.status === 'p2' }">
                {{ r.t2 !== null ? r.t2 : '–' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tv-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: #0f1117;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding:
    max(12px, env(safe-area-inset-top))
    max(16px, env(safe-area-inset-right))
    max(12px, env(safe-area-inset-bottom))
    max(16px, env(safe-area-inset-left));
  --score-scale: 1.35;
}

@media (min-width: 1024px) and (orientation: landscape) {
  .tv-overlay {
    --score-scale: 1.55;
  }
}

.tv-content {
  width: min(920px, 100%);
  max-height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: clamp(12px, 2.5vh, 24px);
}

.tv-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  text-align: center;
}

.event-banner {
  font-size: calc(0.9rem * var(--score-scale));
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: #34d399;
}

.lane-banner {
  font-size: calc(1.05rem * var(--score-scale));
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #60a5fa;
}

.round-label {
  font-size: calc(1.35rem * var(--score-scale));
  font-weight: bold;
  letter-spacing: 1px;
  color: #a78bfa;
}

.scoreboard-grid {
  display: flex;
  flex-direction: column;
  gap: 5px;
  width: min(560px, 100%);
}

.scoreboard-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 52px minmax(0, 1fr);
  gap: clamp(12px, 3vw, 24px);
  align-items: center;
  width: 100%;
}

.scoreboard-rows.tiebreak-scroll {
  max-height: min(280px, 38vh);
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
}

.score-cell {
  text-align: center;
  min-height: calc(52px * var(--score-scale));
  display: flex;
  align-items: center;
  justify-content: center;
}

.score-empty {
  font-size: calc(1.5rem * var(--score-scale));
  font-weight: bold;
  color: #475569;
}

.score-cell.filled .score-readout {
  color: #e2e8f0;
}

.score-readout {
  font-size: calc(1.75rem * var(--score-scale));
  font-weight: bold;
  line-height: 1;
}

.round-num {
  text-align: center;
  font-size: calc(0.9rem * var(--score-scale));
  color: #94a3b8;
}

.total-cell {
  text-align: center;
  font-size: calc(1.9rem * var(--score-scale));
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

.drop-marker {
  font-size: 0.55rem;
  font-weight: bold;
  vertical-align: super;
}

.status-slot {
  min-height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.spectator-winner {
  font-size: calc(1.35rem * var(--score-scale));
  font-weight: bold;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: #34d399;
}

.spectator-status {
  font-size: calc(1rem * var(--score-scale));
  font-weight: bold;
  color: #94a3b8;
  letter-spacing: 0.5px;
}

.results-table-wrap {
  width: 100%;
  overflow-x: auto;
}

.results-table {
  width: 100%;
  border-collapse: collapse;
  font-size: calc(1.1rem * var(--score-scale));
}

.results-table .round-head {
  padding: 10px clamp(12px, 3vw, 28px);
  text-align: center;
  border-bottom: 2px solid #8b5cf6;
  color: #a78bfa;
  white-space: nowrap;
}

.results-table .player-head {
  padding: 10px 12px;
  text-align: left;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: #e2e8f0;
  white-space: nowrap;
}

.results-table .corner {
  border-bottom: 2px solid #8b5cf6;
}

.results-table td {
  padding: 10px clamp(10px, 2.5vw, 24px);
  text-align: center;
  border-bottom: 1px solid #1e293b;
  color: #cbd5e1;
}

.results-table td.winner {
  font-weight: bold;
  color: #6ee7b7;
  background: #064e3b;
}

.coach-return-btn {
  position: fixed;
  top: max(10px, env(safe-area-inset-top));
  right: max(10px, env(safe-area-inset-right));
  z-index: 201;
  min-height: 36px;
  padding: 8px 14px;
  font-size: 0.75rem;
  font-weight: bold;
  letter-spacing: 0.5px;
  text-transform: uppercase;
  background: rgba(6, 95, 70, 0.92);
  border: 1px solid #059669;
  color: #ecfdf5;
  border-radius: 8px;
  cursor: pointer;
  backdrop-filter: blur(4px);
}
</style>
