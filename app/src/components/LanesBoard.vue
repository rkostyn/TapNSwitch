<script setup>
  import { ref, computed, onMounted } from 'vue'
  import { getLaneBoard, assignEventArenas } from '../api'
  import { arenaLabel } from '../venue'

  const emit = defineEmits(['close', 'openEvent'])

  const board = ref(null)
  const loading = ref(true)
  const busy = ref(false)
  const error = ref('')
  const selectedId = ref('')

  const waiting = computed(() => board.value?.waiting ?? [])
  const arenas = computed(() => board.value?.arenas ?? [])
  const needsMore = computed(() => {
    const seen = new Set()
    const extra = []
    for (const arena of arenas.value) {
      const group = arena.group
      if (!group || seen.has(group.event_id)) continue
      seen.add(group.event_id)
      if ((group.arena_ids?.length ?? 0) < (group.suggested_arena_count ?? 1)) extra.push(group)
    }
    return extra
  })
  const selected = computed(() => {
    if (!selectedId.value || !board.value) return null
    return (
      waiting.value.find(group => group.event_id === selectedId.value)
      ?? arenas.value.find(arena => arena.group?.event_id === selectedId.value)?.group
      ?? null
    )
  })

  function groupTitle(group) {
    return group.event_name || 'Untitled group'
  }

  function needsLabel(group) {
    const have = group.arena_ids?.length ?? 0
    const need = group.suggested_arena_count ?? 1
    if (have >= need) return `${have} arena${have === 1 ? '' : 's'}`
    return `needs ${need} arena${need === 1 ? '' : 's'}${have ? `, has ${have}` : ''}`
  }

  function sessionTime(group) {
    if (!group.start_timestamp) return ''
    const date = new Date(group.start_timestamp)
    if (Number.isNaN(date.getTime())) return ''
    return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
  }

  function isSuggested(arena, group) {
    return !!group?.suggested_arena_ids?.includes(arena.arena_id)
  }

  async function load() {
    loading.value = true
    error.value = ''
    try {
      board.value = await getLaneBoard()
      if (selectedId.value) {
        const stillAround = [
          ...waiting.value,
          ...arenas.value.map(arena => arena.group).filter(Boolean),
        ].some(group => group.event_id === selectedId.value)
        if (!stillAround) selectedId.value = ''
      }
    } catch {
      error.value = 'Failed to load lanes.'
    } finally {
      loading.value = false
    }
  }

  onMounted(load)

  function selectGroup(group) {
    selectedId.value = selectedId.value === group.event_id ? '' : group.event_id
    error.value = ''
  }

  function apiError(e, fallback) {
    const detail = e?.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (detail?.message) return detail.message
    return fallback
  }

  async function tapArena(arena) {
    const occupant = arena.group
    if (occupant && selectedId.value && selectedId.value !== occupant.event_id) {
      error.value = `${arena.name} is already used by ${occupant.event_name}. Clear it first.`
      return
    }

    const group = occupant && selectedId.value === occupant.event_id
      ? occupant
      : selected.value
    if (!group) {
      if (occupant) selectGroup(occupant)
      else error.value = 'Pick a waiting group, then tap a color.'
      return
    }

    const alreadyHere = group.arena_ids?.includes(arena.arena_id)
    const nextIds = alreadyHere
      ? group.arena_ids.filter(id => id !== arena.arena_id)
      : [...(group.arena_ids ?? []), arena.arena_id]

    busy.value = true
    error.value = ''
    try {
      await assignEventArenas(group.event_id, nextIds)
      await load()
    } catch (e) {
      error.value = apiError(e, 'Could not assign that arena.')
    } finally {
      busy.value = false
    }
  }

  function openGroup(group) {
    emit('openEvent', group.event_id)
  }
</script>

<template>
  <Teleport to="body">
    <div class="modal-overlay" @click.self="emit('close')">
      <div class="modal lanes-modal">
        <div class="modal-header">
          <div>
            <h2 class="modal-title">Lanes</h2>
            <p class="venue-line">{{ board?.venue ?? 'Baltimore Urban Axes' }} · 6 arenas · 2 lanes each</p>
          </div>
          <button class="modal-cancel back-btn" @click="emit('close')">Close</button>
        </div>

        <p class="help">
          Each color is an arena. Each arena has two lanes so two people can throw at the same time.
          Sync Checkfront, pick a group, then tap a color to send them there.
        </p>

        <p v-if="error" class="modal-error">{{ error }}</p>
        <div v-if="loading" class="state-msg">Loading…</div>

        <div v-else class="lanes-layout">
          <section class="waiting-col">
            <h3 class="section-title">Waiting</h3>
            <p v-if="waiting.length === 0 && needsMore.length === 0" class="state-msg">Every group has a color.</p>
            <ul class="waiting-list">
              <li
                v-for="group in waiting"
                :key="group.event_id"
                class="waiting-item"
                :class="{ selected: selectedId === group.event_id }"
                @click="selectGroup(group)"
              >
                <span class="waiting-name">{{ groupTitle(group) }}</span>
                <span class="waiting-meta">
                  {{ group.players.length }} players
                  <span v-if="group.checkfront_booking_code"> · {{ group.checkfront_booking_code }}</span>
                  <span v-if="sessionTime(group)"> · {{ sessionTime(group) }}</span>
                </span>
                <span class="waiting-need">{{ needsLabel(group) }}</span>
              </li>
              <li
                v-for="group in needsMore"
                :key="`more-${group.event_id}`"
                class="waiting-item"
                :class="{ selected: selectedId === group.event_id }"
                @click="selectGroup(group)"
              >
                <span class="waiting-name">{{ groupTitle(group) }}</span>
                <span class="waiting-meta">Already on {{ arenaLabel(group.arena_ids) }}</span>
                <span class="waiting-need">{{ needsLabel(group) }}</span>
              </li>
            </ul>
            <p v-if="selected" class="selected-hint">
              {{ groupTitle(selected) }} selected — tap a color to assign.
              <button class="text-btn" @click="openGroup(selected)">Open group</button>
            </p>
          </section>

          <section class="floor">
            <button
              v-for="arena in arenas"
              :key="arena.arena_id"
              class="arena-card"
              :class="{
                open: !arena.group,
                occupied: !!arena.group,
                selected: selectedId && arena.group?.event_id === selectedId,
                suggested: isSuggested(arena, selected),
                black: arena.arena_id === 'black',
              }"
              :style="{ '--arena': arena.color, '--arena-text': arena.text_color }"
              :disabled="busy"
              @click="tapArena(arena)"
            >
              <span class="arena-name">{{ arena.name }}</span>
              <span class="lane-row">
                <span v-for="lane in arena.lanes" :key="lane.lane_id" class="lane-pill">{{ lane.label }}</span>
              </span>
              <span v-if="arena.group" class="arena-group">
                {{ groupTitle(arena.group) }}
                <span class="arena-group-meta">{{ arena.group.players.length }} players</span>
              </span>
              <span v-else class="arena-open">Open</span>
              <span v-if="isSuggested(arena, selected) && !arena.group" class="suggest-tag">Checkfront hint</span>
              <span v-else-if="arena.group && (arena.group.arena_ids?.length ?? 0) < (arena.group.suggested_arena_count ?? 1)" class="suggest-tag">
                {{ needsLabel(arena.group) }}
              </span>
            </button>
          </section>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.lanes-modal {
  width: min(980px, 96vw);
  max-height: 90vh;
  overflow-y: auto;
}

.venue-line,
.help,
.selected-hint,
.waiting-meta,
.waiting-need,
.arena-group-meta,
.arena-open,
.suggest-tag {
  color: var(--color-muted);
}

.venue-line {
  margin: 4px 0 0;
  font-size: 0.8rem;
}

.help {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.4;
}

.back-btn {
  padding: 6px 14px;
  font-size: 0.8rem;
}

.state-msg {
  color: #475569;
  font-size: 0.95rem;
  padding: 8px 0;
}

.lanes-layout {
  display: grid;
  grid-template-columns: minmax(220px, 280px) 1fr;
  gap: 20px;
}

.section-title {
  margin: 0 0 8px;
  font-size: 0.85rem;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 1px;
  color: var(--color-purple);
}

.waiting-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.waiting-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  background: var(--color-bg-input);
  border: 1px solid var(--color-bg-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
}

.waiting-item.selected,
.arena-card.selected {
  border-color: var(--color-purple);
  box-shadow: 0 0 0 1px var(--color-purple);
}

.waiting-name,
.arena-group {
  font-weight: bold;
  color: var(--color-text);
}

.waiting-meta,
.waiting-need,
.arena-group-meta {
  font-size: 0.75rem;
}

.tv-link {
  display: inline-block;
  margin-top: 6px;
  padding: 2px 8px;
  font-size: 0.7rem;
  font-weight: bold;
  letter-spacing: 0.08em;
  color: #93c5fd;
  border: 1px solid #1d4ed8;
  border-radius: 999px;
  text-decoration: none;
}

.selected-hint {
  margin: 10px 0 0;
  font-size: 0.8rem;
}

.text-btn {
  margin-left: 8px;
  padding: 0;
  background: none;
  border: none;
  color: var(--color-purple);
  font: inherit;
  font-weight: bold;
  cursor: pointer;
}

.floor {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.arena-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  min-height: 140px;
  padding: 14px;
  border-radius: var(--radius-lg);
  border: 2px solid var(--arena);
  background: #16181f;
  color: var(--color-text);
  text-align: left;
  cursor: pointer;
  font: inherit;
}

.arena-card:disabled {
  opacity: 0.6;
  cursor: wait;
}

.arena-card.suggested {
  box-shadow: 0 0 0 2px #fbbf24;
}

/* Black on the dark board: light name, gray outline, still darker than White. */
.arena-card.black {
  border-color: #9ca3af;
  background: #0b0c10;
}

.arena-card.black .arena-name {
  color: #f8fafc;
}

.arena-card.black .lane-pill {
  background: #111111;
  color: #f8fafc;
  box-shadow: inset 0 0 0 1px #9ca3af;
}

.arena-card.black .arena-open {
  color: #e5e7eb;
}

.arena-name {
  font-size: 1.1rem;
  font-weight: bold;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--arena);
}

.lane-row {
  display: flex;
  gap: 6px;
}

.lane-pill {
  padding: 2px 8px;
  font-size: 0.7rem;
  font-weight: bold;
  border-radius: 999px;
  background: var(--arena);
  color: var(--arena-text);
}

.arena-open {
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.suggest-tag {
  font-size: 0.7rem;
  font-weight: bold;
  text-transform: uppercase;
}

@media (max-width: 760px) {
  .lanes-layout {
    grid-template-columns: 1fr;
  }

  .floor {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
