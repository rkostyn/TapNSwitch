<script setup>
  import { ref } from 'vue'
  import ScoreBoard from './components/ScoreBoard.vue'
  import AppHeader from './components/AppHeader.vue'

  const totalRounds = ref(3)
  const player1Name = ref('Player 1')
  const player2Name = ref('Player 2')

  const showConfig = ref(true)
  const configRounds = ref(3)
  const configP1 = ref('Player 1')
  const configP2 = ref('Player 2')

  const scoreboard = ref(null)

  function openConfig() {
    configRounds.value = totalRounds.value
    configP1.value = player1Name.value
    configP2.value = player2Name.value
    showConfig.value = true
  }

  function applyConfig() {
    totalRounds.value = configRounds.value
    player1Name.value = configP1.value || 'Player 1'
    player2Name.value = configP2.value || 'Player 2'
    showConfig.value = false
    scoreboard.value.resetGame()
  }
</script>

<template>
  <div class="page">
    <AppHeader @openConfig="openConfig" />

    <div class="content">
      <ScoreBoard
        ref="scoreboard"
        :player1Name="player1Name"
        :player2Name="player2Name"
        :totalRounds="totalRounds"
        @requestConfig="openConfig"
      />
    </div>

    <Teleport to="body">
      <div v-if="showConfig" class="modal-overlay" @click.self="showConfig = false">
        <div class="modal">
          <h2 class="modal-title">Match Settings</h2>

          <label class="modal-label">Player 1 Name</label>
          <input class="modal-input" v-model="configP1" placeholder="Player 1" />

          <label class="modal-label">Player 2 Name</label>
          <input class="modal-input" v-model="configP2" placeholder="Player 2" />

          <label class="modal-label">Number of Rounds</label>
          <input class="modal-input" type="number" v-model.number="configRounds" min="1" max="10" />

          <p class="modal-warning">Applying settings will reset the current match.</p>

          <div class="modal-actions">
            <button class="modal-cancel" @click="showConfig = false">Cancel</button>
            <button class="modal-apply" @click="applyConfig">Apply & Reset</button>
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


.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal {
  background: #1e2028;
  border-radius: 12px;
  padding: 32px;
  width: 360px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}

.modal-title {
  font-size: 1.2rem;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 2px;
  color: #a78bfa;
  margin: 0 0 8px;
}

.modal-label {
  font-size: 0.85rem;
  font-weight: bold;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 1px;
  margin-top: 6px;
}

.modal-input {
  padding: 8px 12px;
  font-size: 1rem;
  border: 1px solid #334155;
  border-radius: 6px;
  outline: none;
  background: #0f1117;
  color: #e2e8f0;
}

.modal-input:focus {
  border-color: #8b5cf6;
}

.modal-warning {
  font-size: 0.8rem;
  color: #f87171;
  margin: 4px 0 0;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}

.modal-cancel {
  padding: 8px 18px;
  font-size: 0.95rem;
  background: #1e293b;
  color: #94a3b8;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.modal-cancel:hover { background: #293548; }

.modal-apply {
  padding: 8px 18px;
  font-size: 0.95rem;
  font-weight: bold;
  background: #7c3aed;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.modal-apply:hover { background: #6d28d9; }
</style>
