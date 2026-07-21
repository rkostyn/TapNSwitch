<script setup>
  import { ref, computed, onMounted } from 'vue'
  import {
    getEvent,
    addPlayer,
    removePlayer,
    setPlayerLate,
    updateSwissConfig,
    generateSwissMatches,
    generateSwissScores,
    generateBracket,
    getMatchesByEvent,
    lockMatch,
    updateMatchRounds,
    finishEvent,
  } from '../api'
  import { getOrCreateClientId } from '../clientId'
  import { GHOST_PLAYER_ID, GHOST_DISPLAY_NAME } from '../config'
  import BracketView from './BracketView.vue'

  const props = defineProps(['eventId'])
  const emit = defineEmits(['back', 'selectMatch'])

  const clientId = getOrCreateClientId()

  const event = ref(null)
  const matches = ref([])
  const loading = ref(true)
  const error = ref('')
  const busy = ref(false)

  // 'swiss' | 'bracket' — bracket becomes the default once it exists
  const activeTab = ref('swiss')

  // Players collapse out of the way once the swiss stage is generated, but
  // stay reachable so late arrivals can still be marked
  const playersCollapsed = ref(false)

  const newPlayer = ref('')
  const configMatches = ref(2)
  const configRounds = ref(2)

  // After Swiss matches exist, adding a player re-opens the generate controls so
  // the schedule can be rebuilt to include them.
  const needsRegen = ref(false)

  const showBracketPrompt = ref(false)
  const bracketRounds = ref(3)

  // Takeover state: a match another device holds, awaiting override confirmation
  const takeover = ref(null) // { match, lockedBy }
  // Close-event confirmation
  const closing = ref(false)

  const swissMatches = computed(() => matches.value.filter(m => m.match_type === 'swiss'))

  // Upcoming matches first, late throwers' matches next, completed at the
  // bottom — so whoever is up next is always at the top of the list
  const sortedSwissMatches = computed(() => {
    const late = new Set(event.value?.late_players ?? [])
    const rank = m => m.is_finished ? 2 : (late.has(m.player_1_id) || late.has(m.player_2_id) ? 1 : 0)
    return [...swissMatches.value].sort((a, b) => rank(a) - rank(b) || a.sequence - b.sequence)
  })

  const lateMatch = m => {
    const late = new Set(event.value?.late_players ?? [])
    return !m.is_finished && (late.has(m.player_1_id) || late.has(m.player_2_id))
  }
  const bracketMatches = computed(() => matches.value.filter(m => m.match_type === 'bracket'))
  const swissGenerated = computed(() => !!event.value?.swiss_generated_at)
  const bracketGenerated = computed(() => !!event.value?.bracket_generated_at)
  const standings = computed(() => event.value?.swiss_standings ?? null)

  function holderLabel(lockedBy) {
    if (!lockedBy) return ''
    return lockedBy === clientId ? 'this device' : `device ${lockedBy.slice(0, 8)}`
  }

  async function load() {
    loading.value = true
    error.value = ''
    try {
      event.value = await getEvent(props.eventId)
      matches.value = await getMatchesByEvent(props.eventId)
      configMatches.value = event.value.swiss_matches_per_player
      configRounds.value = event.value.swiss_rounds_per_match
      if (bracketGenerated.value) activeTab.value = 'bracket'
      playersCollapsed.value = swissGenerated.value
    } catch (e) {
      error.value = 'Failed to load event.'
    } finally {
      loading.value = false
    }
  }

  onMounted(load)

  function apiError(e, fallback) {
    const detail = e?.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (detail?.message) return detail.message
    return fallback
  }

  async function run(action, fallback) {
    error.value = ''
    busy.value = true
    try {
      await action()
    } catch (e) {
      error.value = apiError(e, fallback)
    } finally {
      busy.value = false
    }
  }

  async function submitAddPlayer() {
    const name = newPlayer.value.trim()
    if (!name) return
    await run(async () => {
      event.value = await addPlayer(props.eventId, name)
      newPlayer.value = ''
      // A new player needs matches — surface the generate controls again.
      if (swissGenerated.value) needsRegen.value = true
    }, 'Failed to add player.')
  }

  async function removePlayerFromEvent(player) {
    await run(async () => {
      event.value = await removePlayer(props.eventId, player)
      // The schedule no longer matches the roster — offer to rebuild it.
      if (swissGenerated.value) needsRegen.value = true
    }, 'Failed to remove player.')
  }

  async function toggleLate(player) {
    const late = !event.value.late_players.includes(player)
    await run(async () => {
      event.value = await setPlayerLate(props.eventId, player, late)
    }, 'Failed to update player.')
  }

  async function saveConfigAndGenerate() {
    await run(async () => {
      event.value = await updateSwissConfig(props.eventId, configMatches.value, configRounds.value)
      await generateSwissMatches(props.eventId)
      needsRegen.value = false
      await load()
    }, 'Failed to generate swiss matches.')
  }

  // Roster changed after generation: rebuild the schedule (before any scores) or
  // append matches for late entrants (after). Config is left as-is.
  async function regenerateMatches() {
    await run(async () => {
      await generateSwissMatches(props.eventId)
      needsRegen.value = false
      await load()
    }, 'Failed to update swiss matches.')
  }

  async function generateScores() {
    await run(async () => {
      const result = await generateSwissScores(props.eventId)
      event.value = { ...event.value, swiss_standings: result }
    }, 'Failed to generate swiss scores.')
  }

  async function confirmBracket() {
    await run(async () => {
      await generateBracket(props.eventId, bracketRounds.value)
      showBracketPrompt.value = false
      await load()
    }, 'Failed to generate bracket.')
  }

  async function changeMatchRounds(match, rounds) {
    await run(async () => {
      await updateMatchRounds(match.match_id, rounds)
      await load()
    }, 'Failed to update rounds.')
  }

  function displayPlayer(id) {
    if (!id) return 'TBD'
    return id === GHOST_PLAYER_ID ? GHOST_DISPLAY_NAME : id
  }

  function matchLabel(match) {
    return `${displayPlayer(match.player_1_id)} vs ${displayPlayer(match.player_2_id)}`
  }

  function matchStatus(match) {
    if (match.is_finished) return 'finished'
    if (match.is_locked) return 'locked'
    return 'open'
  }

  async function selectMatch(match) {
    if (!match.player_1_id || !match.player_2_id) {
      error.value = 'Both players must be decided before this match can start.'
      return
    }
    // Finished matches open directly — scores stay editable after the fact
    await acquire(match, false)
  }

  async function acquire(match, force) {
    error.value = ''
    busy.value = true
    try {
      const locked = await lockMatch(match.match_id, force)
      emit('selectMatch', { match: locked, event: event.value })
    } catch (e) {
      if (e?.response?.status === 423) {
        takeover.value = { match, lockedBy: e.response.data?.detail?.locked_by ?? 'another coach' }
      } else {
        error.value = apiError(e, 'Failed to select match.')
      }
    } finally {
      busy.value = false
    }
  }

  async function confirmTakeover() {
    const match = takeover.value.match
    takeover.value = null
    await acquire(match, true)
  }

  async function confirmCloseEvent() {
    closing.value = false
    await run(async () => {
      event.value = await finishEvent(props.eventId)
      emit('back')
    }, 'Failed to close the event.')
  }
</script>

<template>
  <div class="event-detail">
    <div class="modal-header">
      <h2 class="modal-title">{{ event?.event_name ?? 'Event' }}</h2>
      <button class="modal-cancel back-btn" @click="emit('back')">Back</button>
    </div>

    <div v-if="loading" class="state-msg">Loading…</div>
    <template v-else-if="event">
      <p v-if="error" class="modal-error">{{ error }}</p>

      <!-- Stage tabs once the bracket exists, so users can go back to swiss -->
      <div v-if="bracketGenerated" class="stage-tabs">
        <button class="stage-tab" :class="{ active: activeTab === 'swiss' }" @click="activeTab = 'swiss'">Swiss</button>
        <button class="stage-tab" :class="{ active: activeTab === 'bracket' }" @click="activeTab = 'bracket'">Bracket</button>
      </div>

      <template v-if="!bracketGenerated || activeTab === 'swiss'">
      <!-- Players (collapsed once the swiss stage is generated, but still
           reachable so late arrivals can be marked) -->
      <section class="section">
        <button
          class="section-title section-toggle"
          :aria-expanded="!playersCollapsed"
          @click="playersCollapsed = !playersCollapsed"
        >
          Players
          <span class="toggle-indicator">{{ playersCollapsed ? '▸' : '▾' }}</span>
        </button>
        <template v-if="!playersCollapsed">
        <p v-if="event.source === 'checkfront'" class="checkfront-players-note">
          Players imported from Checkfront
          <span v-if="event.checkfront_booking_code">({{ event.checkfront_booking_code }})</span>.
          Add names below for extra throwers or walk-ins.
        </p>
        <ul class="player-list">
          <li v-for="player in event.players" :key="player" class="player-item">
            <span class="player-name">
              {{ player }}
              <span v-if="event.late_players.includes(player)" class="late-badge">Late</span>
            </span>
            <span class="player-actions">
              <button
                class="outline-pill-btn late-toggle"
                :disabled="busy || event.is_finished"
                @click="toggleLate(player)"
              >
                {{ event.late_players.includes(player) ? 'Arrived' : 'Mark Late' }}
              </button>
              <button
                class="outline-pill-btn remove-toggle"
                :disabled="busy || event.is_finished"
                title="Remove player"
                @click="removePlayerFromEvent(player)"
              >
                Remove
              </button>
            </span>
          </li>
        </ul>
        <div class="add-player-row" v-if="!event.is_finished">
          <input
            class="modal-input add-player-input"
            v-model="newPlayer"
            placeholder="New player name"
            :disabled="busy"
            @keyup.enter="submitAddPlayer"
          />
          <button class="modal-submit" :disabled="busy || !newPlayer.trim()" @click="submitAddPlayer">Add</button>
        </div>
        </template>
      </section>

      <!-- Swiss setup / matches -->
      <section class="section">
        <h3 class="section-title">Swiss Stage</h3>
        <template v-if="!swissGenerated">
          <div class="config-row">
            <label class="modal-label">Matches per thrower</label>
            <input class="modal-input config-input" type="number" min="1" max="20" v-model.number="configMatches" />
          </div>
          <div class="config-row">
            <label class="modal-label">Rounds per match</label>
            <input class="modal-input config-input" type="number" min="1" max="10" v-model.number="configRounds" />
          </div>
          <button class="modal-submit full-btn" :disabled="busy || event.players.length < 2" @click="saveConfigAndGenerate">
            Generate Swiss Matches
          </button>
        </template>
        <template v-else>
          <div v-if="needsRegen" class="regen-block">
            <p class="regen-note">
              Roster changed — update the matches to include everyone. Scores already entered are kept;
              new players get matches added.
            </p>
            <button class="modal-submit full-btn" :disabled="busy || event.players.length < 2" @click="regenerateMatches">
              Update Swiss Matches
            </button>
            <button class="modal-cancel full-btn" :disabled="busy" @click="needsRegen = false">
              Cancel
            </button>
          </div>
          <ul class="match-list">
            <li
              v-for="match in sortedSwissMatches"
              :key="match.match_id"
              class="match-item"
              :class="matchStatus(match)"
              role="button"
              tabindex="0"
              @click="selectMatch(match)"
              @keydown.enter.prevent="selectMatch(match)"
              @keydown.space.prevent="selectMatch(match)"
            >
              <span class="match-name">{{ matchLabel(match) }}</span>
              <span class="match-status">
                <template v-if="match.is_finished">{{ match.winner_id ? `Won: ${match.winner_id}` : 'Finished' }}</template>
                <template v-else-if="match.is_locked">In use by {{ holderLabel(match.locked_by) }}</template>
                <template v-else-if="lateMatch(match)">Delayed — late thrower</template>
                <template v-else>Open</template>
              </span>
            </li>
          </ul>
          <button class="modal-submit full-btn" :disabled="busy" @click="generateScores">
            Generate Swiss Scores
          </button>
        </template>
      </section>

      <!-- Standings -->
      <section class="section" v-if="standings">
        <h3 class="section-title">Swiss Standings</h3>
        <table class="standings-table">
          <thead>
            <tr><th>#</th><th>Thrower</th><th>Points</th><th>Rounds Won</th><th>Best Round</th></tr>
          </thead>
          <tbody>
            <tr v-for="(s, i) in standings" :key="s.player">
              <td>{{ i + 1 }}</td>
              <td>{{ s.player }}</td>
              <td>{{ s.points }}</td>
              <td>{{ s.rounds_won }}</td>
              <td>{{ s.highest_round }}</td>
            </tr>
          </tbody>
        </table>

        <template v-if="!bracketGenerated">
          <button v-if="!showBracketPrompt" class="modal-submit full-btn" :disabled="busy" @click="showBracketPrompt = true; bracketRounds = 3">
            Generate Tournament Bracket
          </button>
          <div v-else class="bracket-prompt">
            <label class="modal-label">Rounds per tournament match</label>
            <input class="modal-input config-input" type="number" min="1" max="10" v-model.number="bracketRounds" />
            <div class="modal-actions">
              <button class="modal-cancel" :disabled="busy" @click="showBracketPrompt = false">Cancel</button>
              <button class="modal-submit" :disabled="busy" @click="confirmBracket">Start Bracket</button>
            </div>
          </div>
        </template>
      </section>
      </template>

      <!-- Bracket -->
      <section class="section" v-if="bracketGenerated && activeTab === 'bracket'">
        <h3 class="section-title">Tournament Bracket</h3>
        <BracketView :matches="bracketMatches" @select="selectMatch" @updateRounds="changeMatchRounds" />
      </section>

      <button
        v-if="!event.is_finished"
        class="modal-cancel close-event-btn"
        :disabled="busy"
        @click="closing = true"
      >Close Event</button>
    </template>

    <!-- Close event confirmation -->
    <div v-if="closing" class="confirm-box">
      <p class="confirm-text">
        Close <strong>{{ event?.event_name }}</strong>? Scores can no longer be changed and the event is hidden from the list.
      </p>
      <div class="modal-actions">
        <button class="modal-cancel" @click="closing = false">Cancel</button>
        <button class="modal-submit danger" @click="confirmCloseEvent">Close Event</button>
      </div>
    </div>

    <!-- Lock takeover notice -->
    <div v-if="takeover" class="confirm-box">
      <p class="confirm-text">
        This match is already being scored on <strong>{{ holderLabel(takeover.lockedBy) }}</strong>.
      </p>
      <div class="modal-actions">
        <button class="modal-cancel" @click="takeover = null">Cancel</button>
        <button class="modal-submit danger" @click="confirmTakeover">Override &amp; Take Over</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.event-detail {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.back-btn {
  padding: 6px 14px;
  font-size: 0.8rem;
}

.state-msg {
  color: #475569;
  font-size: 0.95rem;
  padding: 12px 0;
}

.stage-tabs {
  display: flex;
  border-bottom: 2px solid var(--color-bg-secondary);
}

.stage-tab {
  flex: 1;
  padding: 10px;
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  color: #64748b;
  font-size: 0.85rem;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 1px;
  cursor: pointer;
}

.stage-tab.active {
  color: var(--color-purple);
  border-bottom-color: var(--color-purple);
}

.section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.checkfront-players-note {
  margin: 0;
  font-size: 0.8rem;
  color: var(--color-muted);
  line-height: 1.4;
}

.section-title {
  margin: 0;
  font-size: 0.85rem;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--color-purple);
  border-bottom: 1px solid var(--color-bg-secondary);
  padding-bottom: 4px;
}

.section-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  background: none;
  border: none;
  border-bottom: 1px solid var(--color-bg-secondary);
  padding: 0 0 4px;
  font-family: inherit;
  text-align: left;
  cursor: pointer;
}

.toggle-indicator {
  font-size: 0.8rem;
  color: var(--color-muted);
}

.player-list, .match-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.player-item, .match-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--color-bg-input);
  border: 1px solid var(--color-bg-secondary);
  border-radius: var(--radius-md);
}

.match-item {
  cursor: pointer;
}

.match-item[role="button"]:focus-visible {
  outline: 2px solid var(--color-purple-focus);
  outline-offset: 2px;
}

.match-item:hover {
  border-color: var(--color-purple);
}

.match-item.finished {
  opacity: 0.7;
}

.match-item.locked .match-status {
  color: #fbbf24;
}

.player-name, .match-name {
  font-weight: bold;
  color: var(--color-text);
}

.match-status {
  font-size: 0.75rem;
  color: #94a3b8;
}

.late-badge {
  margin-left: 8px;
  padding: 2px 8px;
  font-size: 0.7rem;
  font-weight: bold;
  text-transform: uppercase;
  background: #3b2800;
  color: #fbbf24;
  border-radius: 10px;
}

.player-actions {
  display: flex;
  gap: 6px;
}

.late-toggle, .remove-toggle {
  font-size: 0.7rem;
  padding: 4px 10px;
}

.remove-toggle {
  color: #f87171;
  border-color: #f87171;
}

.add-player-row {
  display: flex;
  gap: 8px;
}

.add-player-input { flex: 1; }

.config-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.config-row .modal-label { margin: 0; }

.config-input {
  width: 80px;
  text-align: center;
}

.full-btn {
  width: 100%;
}

.regen-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.regen-note {
  margin: 0;
  padding: 8px 12px;
  font-size: 0.8rem;
  color: #fbbf24;
  background: #3b2800;
  border-radius: var(--radius-md);
}

.standings-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}

.standings-table th {
  text-align: left;
  padding: 6px 8px;
  color: var(--color-purple);
  text-transform: uppercase;
  font-size: 0.7rem;
  letter-spacing: 1px;
  border-bottom: 2px solid var(--color-purple);
}

.standings-table td {
  padding: 6px 8px;
  color: var(--color-text);
  border-bottom: 1px solid var(--color-bg-secondary);
}

.standings-table tr:first-child td {
  color: #34d399;
  font-weight: bold;
}

.bracket-prompt {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.confirm-box {
  position: sticky;
  bottom: 0;
  background: var(--color-bg-input);
  border: 1px solid #eab308;
  border-radius: var(--radius-md);
  padding: 12px 16px;
}

.confirm-text {
  margin: 0 0 8px;
  color: var(--color-text);
  font-size: 0.9rem;
}

.modal-submit.danger {
  background: #b45309;
}

.close-event-btn {
  align-self: flex-end;
  font-size: 0.8rem;
  padding: 6px 14px;
}
</style>
