<script setup>
  import { computed } from 'vue'

  const props = defineProps(['matches'])
  const emit = defineEmits(['select', 'updateRounds'])

  const rounds = computed(() => {
    const grouped = {}
    for (const m of props.matches) {
      (grouped[m.bracket_round] ??= []).push(m)
    }
    return Object.keys(grouped)
      .map(Number)
      .sort((a, b) => a - b)
      .map(r => ({ round: r, matches: grouped[r].sort((a, b) => a.bracket_slot - b.bracket_slot) }))
  })

  function roundLabel(roundMatches, round) {
    if (roundMatches.length === 1) return 'Final'
    if (roundMatches.length === 2) return 'Semifinals'
    return `Round ${round}`
  }

  function playerLabel(name) {
    return name ?? 'TBD'
  }

  function changeRounds(match, event) {
    const value = parseInt(event.target.value)
    if (!isNaN(value) && value >= 1 && value !== match.rounds_per_match) {
      emit('updateRounds', match, value)
    }
  }
</script>

<template>
  <div class="bracket">
    <div v-for="col in rounds" :key="col.round" class="bracket-round">
      <div class="bracket-round-label">{{ roundLabel(col.matches, col.round) }}</div>
      <div class="bracket-col">
        <div
          v-for="match in col.matches"
          :key="match.match_id"
          class="bracket-match"
          :class="{ finished: match.is_finished, locked: match.is_locked }"
          @click="emit('select', match)"
        >
          <div class="bracket-player" :class="{ winner: match.winner_id && match.winner_id === match.player_1_id, tbd: !match.player_1_id }">
            {{ playerLabel(match.player_1_id) }}
          </div>
          <div class="bracket-player" :class="{ winner: match.winner_id && match.winner_id === match.player_2_id, tbd: !match.player_2_id }">
            {{ playerLabel(match.player_2_id) }}
          </div>
          <div class="bracket-meta" @click.stop>
            <span v-if="match.is_finished" class="bracket-status done">Final</span>
            <span v-else-if="match.is_locked" class="bracket-status held">{{ match.locked_by }}</span>
            <span v-else class="bracket-status open">Open</span>
            <label class="bracket-rounds-label">
              Rounds
              <input
                class="bracket-rounds-input"
                type="number"
                min="1"
                max="10"
                :value="match.rounds_per_match"
                :disabled="match.is_finished"
                @change="changeRounds(match, $event)"
              />
            </label>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.bracket {
  display: flex;
  gap: 16px;
  align-items: stretch;
  overflow-x: auto;
  padding: 4px 0;
}

.bracket-round {
  display: flex;
  flex-direction: column;
  min-width: 170px;
  flex: 1;
}

.bracket-round-label {
  text-align: center;
  font-size: 0.75rem;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--color-purple);
  margin-bottom: 8px;
}

.bracket-col {
  display: flex;
  flex-direction: column;
  justify-content: space-around;
  gap: 12px;
  flex: 1;
}

.bracket-match {
  background: var(--color-bg-input);
  border: 1px solid var(--color-bg-secondary);
  border-radius: var(--radius-md);
  padding: 8px;
  cursor: pointer;
}

.bracket-match:hover {
  border-color: var(--color-purple);
}

.bracket-match.finished {
  opacity: 0.85;
}

.bracket-player {
  padding: 4px 6px;
  font-size: 0.9rem;
  font-weight: bold;
  color: var(--color-text);
  border-radius: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bracket-player.tbd {
  color: #475569;
  font-weight: normal;
  font-style: italic;
}

.bracket-player.winner {
  color: #34d399;
}

.bracket-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px solid var(--color-bg-secondary);
}

.bracket-status {
  font-size: 0.7rem;
  font-weight: bold;
  text-transform: uppercase;
  padding: 2px 8px;
  border-radius: 10px;
}

.bracket-status.done { background: #022c22; color: #34d399; }
.bracket-status.held { background: #3b2800; color: #fbbf24; }
.bracket-status.open { background: var(--color-bg-secondary); color: #94a3b8; }

.bracket-rounds-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.7rem;
  color: #94a3b8;
}

.bracket-rounds-input {
  width: 44px;
  padding: 2px 4px;
  background: var(--color-bg-secondary);
  color: var(--color-text);
  border: 1px solid var(--color-border-input);
  border-radius: 4px;
  font-size: 0.8rem;
}
</style>
