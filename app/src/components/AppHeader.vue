<script setup>
  import { ref } from 'vue'
  import { login } from '../api'
  import { getCookie, setCookie, deleteCookie } from '../cookies'
  import EventsModal from './EventsModal.vue'

  const emit = defineEmits(['openConfig', 'selectMatch'])

  const showLogin = ref(false)
  const username = ref('')
  const password = ref('')
  const error = ref('')
  const loading = ref(false)
  const loggedInUser = ref(getCookie('username') ?? '')
  const showEvents = ref(false)
  const eventsInitialId = ref(null)

  function openEvents(eventId = null) {
    eventsInitialId.value = eventId
    showEvents.value = true
  }

  defineExpose({ openEvents })

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
    </div>
    <div class="header-right">
      <template v-if="loggedInUser">
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

  <EventsModal v-if="showEvents" :initialEventId="eventsInitialId" @close="showEvents = false" @selectMatch="emit('selectMatch', $event)" />

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
  padding: 0 20px;
  height: 56px;
  background: #13151c;
  border-bottom: 1px solid #1e293b;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
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

.logged-in-user {
  font-size: 0.875rem;
  font-weight: bold;
  color: var(--color-purple);
  padding: 6px 12px;
  background: var(--color-purple-soft);
  border: 1px solid var(--color-purple-edge);
  border-radius: var(--radius-sm);
}
</style>
