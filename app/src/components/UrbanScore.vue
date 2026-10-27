<script setup>
  import { ref, computed, watch } from 'vue'

  const props = defineProps(['playerName', 'mirrored', 'disabled', 'clutchAvailable'])
  const emit = defineEmits(['score'])

  // IATF scoring: a regular axe scores 1, 3, 5, or 0 (hit the board outside
  // the target). A dropped axe also scores 0 but is recorded as a drop. The
  // Clutch circle switches the grid to clutch scoring.
  const regularButtons = [
    { text: '3', value: 3, color: 'red' },
    { text: '1', value: 1, color: 'blue' },
    { text: '0', value: 0, color: 'orange' },
    { text: '5', value: 5, color: 'purple' },
    { clutch: true },
    { text: 'Drop', value: 0, color: 'gray', drop: true },
  ]

  // A called clutch scores 7 or 0 (a miss). The unused circles are greyed out;
  // Drop and Clutch (now Cancel) stay put so they're always where expected.
  const clutchButtons = [
    { text: '0', value: 0, color: 'orange' },
    { text: '7', value: 7, color: 'green' },
    { text: '-', value: 0, color: 'gray', disabled: true },
    { text: '-', value: 0, color: 'gray', disabled: true },
    { clutch: true },
    { text: 'Drop', value: 0, color: 'gray', drop: true },
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
    emit('score', { points: item.value, clutch, drop: !!item.drop })
  }
</script>

<template>
  <div class="urban-score">
    <div class="grid-container">
      <div v-for="(item, idx) in displayButtons" :key="idx" class="grid-child">
        <button
          v-if="item.clutch"
          class="button-circle"
          :class="clutchMode ? 'color-red' : 'color-teal'"
          :disabled="props.disabled || !props.clutchAvailable"
          @click="toggleClutch"
        >{{ clutchMode ? 'Cancel' : 'Clutch' }}</button>
        <button
          v-else
          class="button-circle"
          :class="`color-${item.color}`"
          :disabled="props.disabled || item.disabled"
          @click="pick(item)"
        >{{ item.text }}</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.urban-score {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
}

.grid-container {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  grid-gap: 20px;
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
  width: 106px;
  height: 106px;
  border-radius: 100%;
  border: none;
  font-family: inherit;
  font-size: 1.32rem;
  font-weight: bold;
  color: #fff;
  cursor: pointer;
}

.button-circle:active {
  transition: 0.3s;
  transform: scale(1.13);
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
.color-teal   { background: #047857; }
</style>
