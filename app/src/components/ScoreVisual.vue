<script setup>
  import { computed } from 'vue'

  const props = defineProps({
    leftName: { type: String, default: 'Player 1' },
    rightName: { type: String, default: 'Player 2' },
    player1Name: { type: String, default: '' },
    player2Name: { type: String, default: '' },
    leftScores: { type: Array, default: () => [] },
    rightScores: { type: Array, default: () => [] },
    displayRound: { type: Number, default: 1 },
    totalRounds: { type: Number, default: 3 },
    showTiebreak: { type: Boolean, default: false },
    roundRows: { type: Array, default: () => [] },
  })

  function throwTotal(scores) {
    return (scores ?? []).reduce((sum, item) => sum + (item ? item.value : 0), 0)
  }

  const slotCount = computed(() =>
    Math.max(props.leftScores?.length ?? 0, props.rightScores?.length ?? 0, 5)
  )
</script>

<template>
  <div class="score-visual">
    <div class="tab-bar" aria-hidden="true">
      <span class="tab-btn">{{ leftName || 'Player 1' }}</span>
      <span class="tab-btn active">Scores</span>
      <span class="tab-btn">{{ rightName || 'Player 2' }}</span>
    </div>

    <div class="scoreboard">
      <span class="round-label">
        {{ showTiebreak ? 'Tie Breaker' : `Round ${displayRound} of ${totalRounds}` }}
      </span>

      <div class="scoreboard-grid">
        <div class="scoreboard-row scoreboard-head">
          <div class="col-header">{{ leftName || 'Player 1' }}</div>
          <div class="col-header round-col-label">{{ showTiebreak ? '#' : 'Axe' }}</div>
          <div class="col-header">{{ rightName || 'Player 2' }}</div>
        </div>

        <div class="scoreboard-row" v-for="i in slotCount" :key="i">
          <div class="score-cell" :class="{ filled: leftScores[i - 1] }">
            <template v-if="leftScores[i - 1]">
              {{ leftScores[i - 1].value }}<sup v-if="leftScores[i - 1].drop" class="drop-marker">d</sup>
            </template>
            <template v-else>–</template>
          </div>
          <div class="round-num">{{ i }}</div>
          <div class="score-cell" :class="{ filled: rightScores[i - 1] }">
            <template v-if="rightScores[i - 1]">
              {{ rightScores[i - 1].value }}<sup v-if="rightScores[i - 1].drop" class="drop-marker">d</sup>
            </template>
            <template v-else>–</template>
          </div>
        </div>

        <div class="scoreboard-row scoreboard-total">
          <div class="total-cell">{{ throwTotal(leftScores) }}</div>
          <div class="total-label">Total</div>
          <div class="total-cell">{{ throwTotal(rightScores) }}</div>
        </div>
      </div>
    </div>

    <table v-if="roundRows.length" class="results-table">
      <thead>
        <tr>
          <th class="corner"></th>
          <th v-for="row in roundRows" :key="row.round" class="round-head">Round {{ row.round }}</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th class="player-head">{{ player1Name || leftName || 'Player 1' }}</th>
          <td
            v-for="row in roundRows"
            :key="`p1-${row.round}`"
            :class="{ winner: row.status === 'p1' }"
          >{{ row.t1 ?? '–' }}</td>
        </tr>
        <tr>
          <th class="player-head">{{ player2Name || rightName || 'Player 2' }}</th>
          <td
            v-for="row in roundRows"
            :key="`p2-${row.round}`"
            :class="{ winner: row.status === 'p2' }"
          >{{ row.t2 ?? '–' }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.score-visual {
  width: min(520px, 94vw);
  display: flex;
  flex-direction: column;
  align-items: center;
}

.tab-bar {
  display: flex;
  width: 100%;
  border-bottom: 2px solid #334155;
  margin-bottom: 8px;
}

.tab-btn {
  flex: 1;
  padding: 10px;
  color: #64748b;
  font-size: 0.85rem;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 1px;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tab-btn.active {
  color: #a78bfa;
  border-bottom: 2px solid #a78bfa;
  margin-bottom: -2px;
}

.scoreboard {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 16px;
  box-sizing: border-box;
  width: 100%;
}

.round-label {
  font-size: 1.2rem;
  font-weight: bold;
  letter-spacing: 1px;
  color: #a78bfa;
  margin-bottom: 40px;
}

.scoreboard-grid {
  display: flex;
  flex-direction: column;
  gap: 5px;
  width: 100%;
}

.scoreboard-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 48px minmax(0, 1fr);
  gap: 20px;
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
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.score-cell.filled {
  color: #e2e8f0;
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

.drop-marker {
  font-size: 0.55rem;
  font-weight: bold;
  vertical-align: super;
}

.results-table {
  border-collapse: collapse;
  font-size: 1.15rem;
  margin-top: 12px;
}

.results-table .round-head {
  padding: 12px 42px;
  text-align: center;
  border-bottom: 2px solid #8b5cf6;
  font-size: 1.25rem;
  color: #a78bfa;
  white-space: nowrap;
}

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
</style>
