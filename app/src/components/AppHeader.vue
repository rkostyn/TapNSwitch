<script setup>
  import { ref, onMounted, onUnmounted, watch } from 'vue'
  import { login, getActiveCheckfrontEvents, getCheckfrontStatus, syncCheckfrontBookings } from '../api'
  import { getCookie, setCookie, deleteCookie } from '../cookies'
  import { getOrCreateClientId } from '../clientId'
  import EventsModal from './EventsModal.vue'

  const clientId = getOrCreateClientId()
  const shortClientId = clientId.slice(0, 8)

  const emit = defineEmits(['openConfig', 'selectMatch', 'selectGroup'])

  const showLogin = ref(false)
  const username = ref('')
  const password = ref('')
  const error = ref('')
  const loading = ref(false)
  const loggedInUser = ref(getCookie('username') ?? '')
  const showEvents = ref(false)
  const eventsInitialId = ref(null)

  const checkfrontGroups = ref([])
  const selectedGroupId = ref('')
  const groupsLoading = ref(false)
  const checkfrontStatus = ref(null)
  const syncLoading = ref(false)
  const syncMessage = ref('')
  let groupsPollTimer = null
  let syncMessageTimer = null

  function groupLabel(event) {
    const code = event.checkfront_booking_code ? ` · ${event.checkfront_booking_code}` : ''
    const count = event.players?.length ?? 0
    return `${event.event_name} (${count} players${code})`
  }

  async function loadCheckfrontStatus() {
    if (!loggedInUser.value) return
    try {
      checkfrontStatus.value = await getCheckfrontStatus()
    } catch {
      checkfrontStatus.value = null
    }
  }

  function showSyncMessage(message) {
    syncMessage.value = message
    if (syncMessageTimer) clearTimeout(syncMessageTimer)
    syncMessageTimer = setTimeout(() => {
      syncMessage.value = ''
    }, 12000)
  }

  async function syncCheckfront() {
    syncLoading.value = true
    syncMessage.value = ''
    try {
      const result = await syncCheckfrontBookings()
      showSyncMessage(`Synced ${result.synced} · skipped ${result.skipped} · failed ${result.failed}`)
      await loadCheckfrontGroups()
      await loadCheckfrontStatus()
      // Keep Match Settings + open Events detail aligned with refreshed Checkfront rosters
      if (selectedGroupId.value) {
        const group = checkfrontGroups.value.find(g => g.event_id === selectedGroupId.value) ?? null
        emit('selectGroup', group)
        if (group?.event_id && showEvents.value) {
          openEvents(group.event_id)
        }
      }
    } catch (e) {
      const detail = e?.response?.data?.detail
      if (e?.response?.status === 503) {
        showSyncMessage('Checkfront credentials are not configured on the server.')
      } else if (typeof detail === 'string') {
        showSyncMessage(detail)
      } else {
        showSyncMessage('Checkfront sync failed. Check server logs.')
      }
    } finally {
      syncLoading.value = false
    }
  }

  async function loadCheckfrontGroups() {
    if (!loggedInUser.value) return
    groupsLoading.value = true
    try {
      const groups = await getActiveCheckfrontEvents()
      checkfrontGroups.value = groups
      if (selectedGroupId.value && !groups.some(g => g.event_id === selectedGroupId.value)) {
        selectedGroupId.value = ''
        emit('selectGroup', null)
      }
    } catch {
      // Keep last known groups if refresh fails mid-shift
    } finally {
      groupsLoading.value = false
    }
  }

  function onGroupChange() {
    const group = checkfrontGroups.value.find(g => g.event_id === selectedGroupId.value) ?? null
    emit('selectGroup', group)
    // Open the Checkfront event roster so Players matches the selected booking
    if (group?.event_id) {
      openEvents(group.event_id)
    }
  }

  function startGroupsPoll() {
    stopGroupsPoll()
    groupsPollTimer = setInterval(loadCheckfrontGroups, 30000)
  }

  function stopGroupsPoll() {
    if (groupsPollTimer) {
      clearInterval(groupsPollTimer)
      groupsPollTimer = null
    }
  }

  watch(loggedInUser, (user) => {
    if (user) {
      loadCheckfrontStatus()
      loadCheckfrontGroups()
      startGroupsPoll()
    } else {
      stopGroupsPoll()
      checkfrontGroups.value = []
      selectedGroupId.value = ''
      checkfrontStatus.value = null
      syncMessage.value = ''
      emit('selectGroup', null)
    }
  }, { immediate: true })

  onMounted(() => {
    if (loggedInUser.value) {
      loadCheckfrontStatus()
      loadCheckfrontGroups()
    }
  })

  onUnmounted(() => {
    stopGroupsPoll()
    if (syncMessageTimer) clearTimeout(syncMessageTimer)
  })

  function openEvents(eventId = null) {
    eventsInitialId.value = eventId
    showEvents.value = true
  }

  function onEventsClose() {
    showEvents.value = false
    loadCheckfrontGroups()
  }

  defineExpose({ openEvents, loadCheckfrontGroups })

  function openLogin() {
    username.value = ''
    password.value = ''
    error.value = ''
    showLogin.value = true
  }

  function logout() {
    deleteCookie('access_token')
    deleteCookie('token_type')
    deleteCookie('username')
    deleteCookie('token_issued_at')
    loggedInUser.value = ''
  }

  async function submitLogin() {
    error.value = ''
    loading.value = true
    try {
      const data = await login(username.value, password.value)
      setCookie('access_token', data.access_token, data.expires_in)
      setCookie('token_type', data.token_type, data.expires_in)
      setCookie('username', username.value, data.expires_in)
      setCookie('token_issued_at', String(Date.now()), data.expires_in)
      loggedInUser.value = username.value
      showLogin.value = false
    } catch (e) {
      if (e?.response?.status === 401) {
        error.value = 'Wrong password. Please check your password and try again.'
      } else if (e?.response) {
        const detail = e.response.data?.detail
        error.value = typeof detail === 'string' ? detail : 'Login failed. Please try again.'
      } else {
        error.value = 'Could not reach the server.'
      }
    } finally {
      loading.value = false
    }
  }
</script>

<template>
  <header class="app-header">
    <div class="header-left">
      <button v-if="loggedInUser" class="auth-btn events-btn" @click="openEvents()">Events</button>
      <label v-if="loggedInUser" class="group-picker">
        <span class="group-picker-label">Group</span>
        <select
          class="group-picker-select"
          v-model="selectedGroupId"
          @change="onGroupChange"
          :disabled="groupsLoading && checkfrontGroups.length === 0"
        >
          <option value="">
            {{ checkfrontGroups.length ? 'Select Checkfront group…' : 'No Checkfront groups yet' }}
          </option>
          <option v-for="group in checkfrontGroups" :key="group.event_id" :value="group.event_id">
            {{ groupLabel(group) }}
          </option>
        </select>
      </label>
      <button
        v-if="loggedInUser"
        class="auth-btn sync-btn"
        @click="syncCheckfront"
        :disabled="syncLoading"
        :title="checkfrontStatus?.configured === false
          ? 'Checkfront API credentials may not be set on the server — tap to retry'
          : 'Pull today\'s bookings from Checkfront now'"
      >
        {{ syncLoading ? 'Syncing…' : 'Sync' }}
      </button>
      <span v-if="loggedInUser && syncMessage" class="sync-message" :title="syncMessage">{{ syncMessage }}</span>
    </div>
    <div class="header-right">
      <template v-if="loggedInUser">
        <span class="client-id-chip" :title="`This device: ${clientId}`">{{ shortClientId }}</span>
        <span class="logged-in-user">{{ loggedInUser }}</span>
        <button class="auth-btn logout-btn" @click="logout">Log Out</button>
      </template>
      <template v-else>
        <button class="auth-btn login-btn" @click="openLogin">Log In</button>
        <button class="auth-btn register-btn">Register</button>
      </template>
      <button class="config-btn" @click="emit('openConfig')">&#9881;</button>
    </div>
  </header>

  <EventsModal
    v-if="showEvents"
    :key="eventsInitialId ?? 'events-list'"
    :initialEventId="eventsInitialId"
    @close="onEventsClose"
    @selectMatch="emit('selectMatch', $event)"
  />

  <Teleport to="body">
    <div v-if="showLogin" class="modal-overlay" @click.self="showLogin = false">
      <div class="modal">
        <h2 class="modal-title">Log In</h2>

        <label class="modal-label">Username</label>
        <input
          class="modal-input"
          v-model="username"
          placeholder="Username"
          autocomplete="username"
          :disabled="loading"
        />

        <label class="modal-label">Password</label>
        <input
          class="modal-input"
          type="password"
          v-model="password"
          placeholder="Password"
          autocomplete="current-password"
          :disabled="loading"
          @keyup.enter="submitLogin"
        />

        <p v-if="error" class="modal-error">{{ error }}</p>

        <div class="modal-actions">
          <button class="modal-cancel" @click="showLogin = false" :disabled="loading">Cancel</button>
          <button class="modal-submit" @click="submitLogin" :disabled="loading">
            {{ loading ? 'Logging in…' : 'Log In' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 50;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 20px;
  min-height: 56px;
  background: #13151c;
  border-bottom: 1px solid #1e293b;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 12px;
  min-width: 0;
  flex: 1 1 auto;
}

.group-picker {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.group-picker-label {
  font-size: 0.75rem;
  font-weight: bold;
  text-transform: uppercase;
  color: var(--color-muted);
  flex-shrink: 0;
}

.group-picker-select {
  min-width: 180px;
  max-width: min(420px, 48vw);
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  border: 1px solid #334155;
  background: var(--color-bg-input);
  color: var(--color-text);
  font: inherit;
}

.config-btn {
  width: 34px;
  height: 34px;
  font-size: 1.1rem;
  background: var(--color-bg-secondary);
  color: var(--color-purple);
  border: none;
  border-radius: 50%;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  margin-left: 4px;
}

.config-btn:hover {
  background: var(--color-bg-secondary-hover);
}

.client-id-chip {
  font-size: 0.75rem;
  font-family: monospace;
  color: var(--color-muted);
  padding: 6px 10px;
  background: var(--color-bg-secondary);
  border-radius: var(--radius-sm);
  cursor: default;
}

.logged-in-user {
  font-size: 0.875rem;
  font-weight: bold;
  color: var(--color-purple);
  padding: 6px 12px;
  background: var(--color-purple-soft);
  border: 1px solid var(--color-purple-edge);
  border-radius: var(--radius-sm);
}

.sync-message {
  font-size: 0.75rem;
  color: var(--color-muted);
  max-width: min(320px, 30vw);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
