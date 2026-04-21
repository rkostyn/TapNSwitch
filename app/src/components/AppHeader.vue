<script setup>
  import { ref } from 'vue'
  import axios from 'axios'
  import { config } from '../config'
  import { setCookie } from '../cookies'

  const emit = defineEmits(['openConfig'])

  const showLogin = ref(false)
  const username = ref('')
  const password = ref('')
  const error = ref('')
  const loading = ref(false)

  function openLogin() {
    username.value = ''
    password.value = ''
    error.value = ''
    showLogin.value = true
  }

  async function submitLogin() {
    error.value = ''
    loading.value = true
    try {
      const credentials = btoa(`${username.value}:${password.value}`)
      const { data } = await axios.post(`${config.apiUrl}/auth/login`, { credentials })
      setCookie('access_token', data.access_token, data.expires_in)
      setCookie('token_type', data.token_type, data.expires_in)
      showLogin.value = false
    } catch (e) {
      if (axios.isAxiosError(e) && e.response) {
        error.value = 'Invalid username or password.'
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
    <div class="header-left"></div>
    <div class="header-right">
      <button class="auth-btn login-btn" @click="openLogin">Log In</button>
      <button class="auth-btn register-btn">Register</button>
      <button class="config-btn" @click="emit('openConfig')">&#9881;</button>
    </div>
  </header>

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
  background: #1e293b;
  color: #a78bfa;
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
  background: #273548;
}

.auth-btn {
  padding: 6px 16px;
  font-size: 0.875rem;
  font-weight: bold;
  letter-spacing: 0.5px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.login-btn {
  background: transparent;
  color: #a78bfa;
  border: 1px solid #4c1d95;
}

.login-btn:hover {
  background: #1e1b2e;
}

.register-btn {
  background: #7c3aed;
  color: #fff;
}

.register-btn:hover {
  background: #6d28d9;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
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
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
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

.modal-input:disabled {
  opacity: 0.5;
}

.modal-error {
  font-size: 0.85rem;
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

.modal-cancel:hover:not(:disabled) {
  background: #293548;
}

.modal-submit {
  padding: 8px 18px;
  font-size: 0.95rem;
  font-weight: bold;
  background: #7c3aed;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.modal-submit:hover:not(:disabled) {
  background: #6d28d9;
}

.modal-submit:disabled,
.modal-cancel:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
