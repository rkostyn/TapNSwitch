<script setup>
  import { ref, computed, watch } from 'vue'

  const props = defineProps(['playerName', 'mirrored', 'disabled', 'clutchAvailable'])
  const emit = defineEmits(['score'])

  // A regular axe scores 1–5 or 0.
  const regularButtons = [
    { text: '2', value: 2, color: 'green' },
    { text: '1', value: 1, color: 'blue' },
    { text: '4', value: 4, color: 'purple' },
    { text: '3', value: 3, color: 'red' },
    { text: '0', value: 0, color: 'gray' },
    { text: '5', value: 5, color: 'orange' },
  ]

  // A clutch (final throw only) scores 5, 6, 7 or 0. The clutch scores reuse the
  // same six circles; the two left over are greyed out and non-functioning.
  const clutchButtons = [
    { text: '6', value: 6, color: 'purple' },
    { text: '5', value: 5, color: 'orange' },
    { text: '0', value: 0, color: 'gray' },
    { text: '7', value: 7, color: 'green' },
    { text: '-', value: 0, color: 'gray', disabled: true },
    { text: '-', value: 0, color: 'gray', disabled: true },
  ]

  const clutchMode = ref(false)

  // Clutch can only be called on the final throw; if it stops being available
  // (the side switches, a different cell is selected) fall back to regular.
  watch(() => props.clutchAvailable, (available) => { if (!available) clutchMode.value = false })

  const activeButtons = computed(() => (clutchMode.value ? clutchButtons : regularButtons))

  const displayButtons = computed(() => {
    const src = activeButtons.value
    if (!props.mirrored) return src
    const result = []
    for (let i = 0; i < src.length; i += 2) {
      const a = src[i], b = src[i + 1]
      result.push(...(b !== undefined ? [b, a] : [a]))
    }
    return result
  })

  function toggleClutch() {
    clutchMode.value = !clutchMode.value
  }

  function pick(item) {
    if (item.disabled) return
    const clutch = clutchMode.value
    clutchMode.value = false
    emit('score', { points: item.value, clutch })
  }

  function buttonLabel(item) {
    if (item.disabled) return 'Unavailable'
    const mode = clutchMode.value ? 'clutch ' : ''
    return `${mode}Score ${item.text}`
  }
</script>

<template>
  <div class="urban-score">
    <div class="grid-container" role="group" :aria-label="`${playerName} scoring pad`">
      <div v-for="(item, idx) in displayButtons" :key="idx" class="grid-child">
        <button
          type="button"
          class="button-circle"
          :class="`color-${item.color}`"
          :disabled="props.disabled || item.disabled"
          :aria-label="buttonLabel(item)"
          @click="pick(item)"
        >{{ item.text }}</button>
      </div>
    </div>

    <button
      type="button"
      class="clutch-btn"
      :class="{ active: clutchMode }"
      :disabled="props.disabled || !props.clutchAvailable"
      :aria-pressed="clutchMode"
      :aria-label="clutchMode ? 'Cancel clutch mode' : 'Enable clutch mode for final throw'"
      @click="toggleClutch"
    >{{ clutchMode ? 'Cancel ' : 'Clutch' }}</button>
  </div>
</template>

<style scoped>
.urban-score {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.clutch-btn {
  width: min(232px, 100%);
  min-height: var(--touch-min);
  padding: 16px;
  border: none;
  border-radius: 16px;
  background: #047857;
  color: #fff;
  font-family: inherit;
  font-size: 1.35rem;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 2px;
  cursor: pointer;
}

.clutch-btn.active {
  background: #b91c1c;
}

.clutch-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.grid-container {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: clamp(12px, 3vw, 20px);
  width: min(100%, 260px);
}

.grid-child {
  display: flex;
  justify-content: center;
}

.button-circle {
  display: flex;
  justify-content: center;
  align-items: center;
  text-align: center;
  width: clamp(88px, 24vw, 120px);
  height: clamp(88px, 24vw, 120px);
  border-radius: 100%;
  border: none;
  font-family: inherit;
  font-size: clamp(1.1rem, 3.5vw, 1.45rem);
  font-weight: bold;
  color: #fff;
  cursor: pointer;
}

@media (prefers-reduced-motion: no-preference) {
  .button-circle:active {
    transition: 0.3s;
    transform: scale(1.08);
  }
}

.button-circle:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.color-blue   { background: #3b82f6; }
.color-red    { background: #ef4444; }
.color-purple { background: #8b5cf6; }
.color-orange { background: #f59e0b; }
.color-green  { background: #059669; }
.color-gray   { background: #6b7280; }
</style>
