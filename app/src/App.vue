<script setup>
  import { ref, nextTick, computed } from 'vue'
  import ScoreBoard from './components/ScoreBoard.vue'
  import AppHeader from './components/AppHeader.vue'
  import { GHOST_PLAYER_ID, GHOST_DISPLAY_NAME } from './config'

  const displayName = id => (id === GHOST_PLAYER_ID ? GHOST_DISPLAY_NAME : id)

  const totalRounds = ref(3)
  const player1Name = ref('Player 1')
  const player2Name = ref('Player 2')
  const matchContext = ref(null) // { matchId, eventId, player1Id, player2Id, eventName }
  const activeGroup = ref(null)

  const showConfig = ref(true)
  const configRounds = ref(3)
  const configP1 = ref('Player 1')
  const configP2 = ref('Player 2')

  const rosterPlayers = computed(() => activeGroup.value?.players ?? [])
  const useRosterPicker = computed(() => rosterPlayers.value.length >= 2)

  const scoreboard = ref(null)
  const header = ref(null)

  function onSelectGroup(group) {
    activeGroup.value = group
    if (group?.players?.length >= 2) {
      configP1.value = group.players[0]
      configP2.value = group.players[1]
      player1Name.value = group.players[0]
      player2Name.value = group.players[1]
    }
  }

  function openConfig() {
    configRounds.value = totalRounds.value
    configP1.value = player1Name.value
    configP2.value = player2Name.value
    showConfig.value = true
  }

  function applyConfig() {
    matchContext.value = null
    totalRounds.value = configRounds.value
    player1Name.value = configP1.value || 'Player 1'
    player2Name.value = configP2.value || 'Player 2'
    showConfig.value = false
    nextTick(() => scoreboard.value.resetGame())
  }

  function onSelectMatch({ match, event }) {
    player1Name.value = displayName(match.player_1_id)
    player2Name.value = displayName(match.player_2_id)
    totalRounds.value = match.rounds_per_match
    matchContext.value = {
      matchId: match.match_id,
      eventId: match.event_id,
      player1Id: match.player_1_id,
      player2Id: match.player_2_id,
      eventName: event?.event_name ?? '',
      isFinished: match.is_finished,
    }
    showConfig.value = false
  }

  function onMatchDone() {
    const eventId = matchContext.value?.eventId ?? null
    matchContext.value = null
    if (eventId && header.value) {
      header.value.openEvents(eventId)
    } else {
      openConfig()
    }
  }
</script>

<template>
  <div class="page">
    <AppHeader ref="header" @openConfig="openConfig" @selectMatch="onSelectMatch" @selectGroup="onSelectGroup" />

    <div class="content">
      <ScoreBoard
        ref="scoreboard"
        :player1Name="player1Name"
        :player2Name="player2Name"
        :totalRounds="totalRounds"
        :matchContext="matchContext"
        @requestConfig="openConfig"
        @matchDone="onMatchDone"
      />
    </div>

    <Teleport to="body">
      <div v-if="showConfig" class="modal-overlay" @click.self="showConfig = false">
        <div class="modal">
          <h2 class="modal-title">Match Settings</h2>

          <p v-if="activeGroup" class="modal-group-note">
            Group: {{ activeGroup.event_name }}
            <span v-if="activeGroup.checkfront_booking_code">({{ activeGroup.checkfront_booking_code }})</span>
          </p>

          <label class="modal-label">Player 1 Name</label>
          <select v-if="useRosterPicker" class="modal-input" v-model="configP1">
            <option v-for="name in rosterPlayers" :key="`p1-${name}`" :value="name">{{ name }}</option>
          </select>
          <input v-else class="modal-input" v-model="configP1" placeholder="Player 1" />

          <label class="modal-label">Player 2 Name</label>
          <select v-if="useRosterPicker" class="modal-input" v-model="configP2">
            <option v-for="name in rosterPlayers" :key="`p2-${name}`" :value="name">{{ name }}</option>
          </select>
          <input v-else class="modal-input" v-model="configP2" placeholder="Player 2" />

          <label class="modal-label">Number of Rounds</label>
          <input class="modal-input" type="number" v-model.number="configRounds" min="1" max="10" />

          <p class="modal-warning">Applying settings will reset the current match.</p>

          <div class="modal-actions">
            <button class="modal-cancel" @click="showConfig = false">Cancel</button>
            <button class="modal-submit" @click="applyConfig">Apply & Reset</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style>
.page {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  box-sizing: border-box;
}

.content {
  max-width: 1280px;
  width: 100%;
  margin: 0 auto;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  flex: 1;
}

.modal-group-note {
  margin: 0 0 12px;
  font-size: 0.85rem;
  color: #93c5fd;
}
</style>
