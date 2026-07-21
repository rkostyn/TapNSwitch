<script setup>
  import { ref, onMounted } from 'vue'
  import { getVenueArenas, saveVenueArenas } from '../api'

  const emit = defineEmits(['close'])

  const arenas = ref([])
  const loading = ref(true)
  const saving = ref(false)
  const error = ref('')

  function slugify(label) {
    return label.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'lane'
  }

  function uniqueId(label, index) {
    const base = slugify(label)
    const taken = new Set(arenas.value.map((a, i) => (i === index ? null : a.id)).filter(Boolean))
    if (!taken.has(base)) return base
    let n = 2
    while (taken.has(`${base}-${n}`)) n += 1
    return `${base}-${n}`
  }

  async function load() {
    loading.value = true
    error.value = ''
    try {
      arenas.value = (await getVenueArenas()).map(a => ({ ...a }))
    } catch {
      error.value = 'Failed to load venue lanes.'
    } finally {
      loading.value = false
    }
  }

  onMounted(load)

  function addArena() {
    const label = `Lane ${arenas.value.length + 1}`
    arenas.value.push({ id: uniqueId(label, arenas.value.length), label })
  }

  function removeArena(index) {
    if (arenas.value.length <= 1) return
    arenas.value.splice(index, 1)
  }

  function onLabelChange(index) {
    const row = arenas.value[index]
    row.id = uniqueId(row.label, index)
  }

  async function save() {
    error.value = ''
    const cleaned = arenas.value
      .map(a => ({ id: slugify(a.id || a.label), label: a.label.trim() }))
      .filter(a => a.label)
    if (!cleaned.length) {
      error.value = 'Add at least one lane.'
      return
    }
    saving.value = true
    try {
      arenas.value = await saveVenueArenas(cleaned)
      emit('close')
    } catch (e) {
      error.value = e?.response?.data?.detail ?? 'Failed to save lanes.'
    } finally {
      saving.value = false
    }
  }
</script>

<template>
  <Teleport to="body">
    <div class="modal-overlay" @click.self="emit('close')">
      <div class="modal">
        <h2 class="modal-title">Venue Lanes</h2>
        <p class="modal-note">Define the throwing lanes at your venue (e.g. Blue - Left, Black - Right).</p>

        <div v-if="loading" class="state-msg">Loading…</div>
        <template v-else>
          <div v-for="(arena, index) in arenas" :key="index" class="arena-row">
            <input
              class="modal-input arena-label"
              v-model="arena.label"
              placeholder="Lane name"
              :disabled="saving"
              @input="onLabelChange(index)"
            />
            <span class="arena-id">{{ arena.id }}</span>
            <button
              class="remove-btn"
              type="button"
              :disabled="saving || arenas.length <= 1"
              @click="removeArena(index)"
            >✕</button>
          </div>

          <button class="outline-pill-btn" type="button" :disabled="saving" @click="addArena">+ Add Lane</button>
          <p v-if="error" class="modal-error">{{ error }}</p>

          <div class="modal-actions">
            <button class="modal-cancel" :disabled="saving" @click="emit('close')">Cancel</button>
            <button class="modal-submit" :disabled="saving" @click="save">
              {{ saving ? 'Saving…' : 'Save Lanes' }}
            </button>
          </div>
        </template>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal {
  width: min(480px, 94vw);
}

.modal-note {
  margin: 0 0 12px;
  font-size: 0.85rem;
  color: var(--color-muted);
}

.arena-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.arena-label {
  flex: 1;
}

.arena-id {
  font-size: 0.72rem;
  font-family: monospace;
  color: var(--color-muted);
  min-width: 72px;
}

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
}

.remove-btn:hover:not(:disabled) { background: #475569; }
.remove-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.state-msg {
  color: #475569;
  padding: 8px 0;
}
</style>
