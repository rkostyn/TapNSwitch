<script setup>
  import { ref, onMounted } from 'vue'
  import { getEvents, createEvent } from '../api'
  import EventDetail from './EventDetail.vue'

  const props = defineProps(['initialEventId'])
  const emit = defineEmits(['close', 'selectMatch'])

  // views: 'list' | 'create' | 'detail'
  const view = ref(props.initialEventId ? 'detail' : 'list')
  const selectedEventId = ref(props.initialEventId ?? null)

  function openEvent(event) {
    selectedEventId.value = event.event_id
    view.value = 'detail'
  }

  function onSelectMatch(payload) {
    emit('selectMatch', payload)
    emit('close')
  }

  // list state
  const events = ref([])
  const listLoading = ref(true)
  const listError = ref('')

  async function loadEvents() {
    listLoading.value = true
    listError.value = ''
    try {
      events.value = await getEvents()
    } catch (e) {
      listError.value = 'Failed to load events.'
    } finally {
      listLoading.value = false
    }
  }

  onMounted(loadEvents)

  // create state
  const eventName = ref('')
  const players = ref(['', ''])
  const createLoading = ref(false)
  const createError = ref('')

  function addPlayer() {
    players.value.push('')
  }

  function removePlayer(index) {
    players.value.splice(index, 1)
  }

  function openCreate() {
    eventName.value = ''
    players.value = ['', '']
    createError.value = ''
    view.value = 'create'
  }

  async function submitCreate() {
    createError.value = ''
    const name = eventName.value.trim()
    const playerList = players.value.map(p => p.trim()).filter(Boolean)

    if (!name) { createError.value = 'Event name is required.'; return }
    if (playerList.length < 2) { createError.value = 'At least 2 players are required.'; return }

    createLoading.value = true
    try {
      await createEvent(name, playerList)
      await loadEvents()
      view.value = 'list'
    } catch (e) {
      createError.value = e?.response?.data?.detail ?? 'Failed to create event.'
    } finally {
      createLoading.value = false
    }
  }
</script>

<template>
  <Teleport to="body">
    <div class="modal-overlay" @click.self="emit('close')">
      <div class="modal" :class="{ wide: view === 'detail' }">

        <!-- Event detail view -->
        <EventDetail
          v-if="view === 'detail'"
          :eventId="selectedEventId"
          @back="view = 'list'; loadEvents()"
          @selectMatch="onSelectMatch"
        />

        <!-- List view -->
        <template v-else-if="view === 'list'">
          <div class="modal-header">
            <h2 class="modal-title">Events</h2>
            <button class="modal-submit new-event-btn" @click="openCreate">+ New Event</button>
          </div>

          <div v-if="listLoading" class="state-msg">Loading…</div>
          <div v-else-if="listError" class="modal-error">{{ listError }}</div>
          <div v-else-if="events.length === 0" class="state-msg">No events yet.</div>
          <ul v-else class="event-list">
            <li v-for="event in events" :key="event.event_id" class="event-item" @click="openEvent(event)">
              <span class="event-name">{{ event.event_name }}</span>
              <span class="event-players">{{ event.players?.length ?? 0 }} players</span>
            </li>
          </ul>

          <div class="modal-actions">
            <button class="modal-cancel" @click="emit('close')">Close</button>
          </div>
        </template>

        <!-- Create view -->
        <template v-else>
          <div class="modal-header">
            <h2 class="modal-title">New Event</h2>
          </div>

          <label class="modal-label">Event Name</label>
          <input
            class="modal-input"
            v-model="eventName"
            placeholder="Event name"
            :disabled="createLoading"
          />

          <label class="modal-label">Players</label>
          <div class="player-list">
            <div v-for="(_, i) in players" :key="i" class="player-row">
              <input
                class="modal-input player-input"
                v-model="players[i]"
                :placeholder="`Player ${i + 1}`"
                :disabled="createLoading"
              />
              <button
                v-if="players.length > 2"
                class="remove-btn"
                @click="removePlayer(i)"
                :disabled="createLoading"
              >✕</button>
            </div>
          </div>

          <button class="outline-pill-btn add-player-btn" @click="addPlayer" :disabled="createLoading">+ Add Player</button>

          <p v-if="createError" class="modal-error">{{ createError }}</p>

          <div class="modal-actions">
            <button class="modal-cancel" @click="view = 'list'" :disabled="createLoading">Back</button>
            <button class="modal-submit" @click="submitCreate" :disabled="createLoading">
              {{ createLoading ? 'Creating…' : 'Create Event' }}
            </button>
          </div>
        </template>

      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal {
  width: 420px;
  max-height: 85vh;
  overflow-y: auto;
}

.modal.wide {
  width: min(860px, 94vw);
}

.event-item {
  cursor: pointer;
}

.event-item:hover {
  border-color: var(--color-purple);
}

.new-event-btn {
  padding: 6px 14px;
  font-size: 0.8rem;
}

.add-player-btn {
  margin-top: 2px;
}

.state-msg {
  color: #475569;
  font-size: 0.95rem;
  padding: 12px 0;
}

.event-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.event-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--color-bg-input);
  border: 1px solid var(--color-bg-secondary);
  border-radius: var(--radius-md);
}

.event-name {
  font-weight: bold;
  color: var(--color-text);
}

.event-players {
  font-size: 0.8rem;
  color: #475569;
}

.player-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.player-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.player-input { flex: 1; }

.remove-btn {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  font-size: 0.75rem;
  background: var(--color-border-input);
  color: var(--color-muted);
  border: none;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
}

.remove-btn:hover:not(:disabled) { background: #475569; }
</style>
