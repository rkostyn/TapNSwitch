<script setup>
  import { ref, computed } from 'vue'

  const props = defineProps(['playerName', 'mirrored', 'disabled', 'clutchAvailable'])
  const emit = defineEmits(['score'])

  const defaultButtons = [
    { text: '1', score: '1', color: 'blue' },
    { text: '3', score: '3', color: 'red' },
    { text: '5', score: '5', color: 'purple' },
    { text: '0', score: '0', color: 'orange' },
    { text: 'Call Clutch', color: 'green' },
    { text: 'Drop', score: 'Drop', color: 'gray' },
  ]

  const clutchButtons = [
    { text: 'Left Clutch', score: '7', color: 'green' },
    { text: 'Right Clutch', score: '7', color: 'green' },
    { text: '0', score: '0', color: 'orange' },
    { text: 'Drop', score: 'Drop', color: 'gray' },
    { text: 'Cancel', color: 'red' },
  ]

  const buttons = ref([...defaultButtons])

  const displayButtons = computed(() => {
    if (!props.mirrored) return buttons.value
    const result = []
    for (let i = 0; i < buttons.value.length; i += 2) {
      const a = buttons.value[i], b = buttons.value[i + 1]
      result.push(...(b !== undefined ? [b, a] : [a]))
    }
    return result
  })

  function urbanScore(score) {
    if (score === 'Call Clutch') {
      buttons.value = [...clutchButtons]
    } else if (score === 'Cancel') {
      buttons.value = [...defaultButtons]
    } else {
      const value = buttons.value.find(b => b.text === score)?.score ?? score
      buttons.value = [...defaultButtons]
      emit('score', value)
    }
  }
</script>

<template>
  <div class="grid-container">
    <div v-for="item in displayButtons" class="grid-child">
      <button
        class="button-circle"
        :class="`color-${item.color}`"
        :disabled="props.disabled || (item.text === 'Call Clutch' && !props.clutchAvailable)"
        @click="urbanScore(item.text)"
      >{{ item.text }}</button>
    </div>
  </div>
</template>

<style scoped>
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
  width: 125px;
  height: 125px;
  border-radius: 100%;
  border: none;
  font-family: inherit;
  font-size: 1.55rem;
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
</style>
