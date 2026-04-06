<script setup>
  import { ref, computed } from 'vue'

  const props = defineProps(['playerName', 'mirrored', 'disabled', 'clutchAvailable'])
  const emit = defineEmits(['score'])

  const defaultButtons = [
    {text: "1", score: "1", style: { 'background-color': "#3b82f6", color: "#fff" }},
    {text: "3", score: "3", style: { 'background-color': "#ef4444", color: "#fff" }},
    {text: "5", score: "5", style: { 'background-color': "#8b5cf6", color: "#fff" }},
    {text: "0", score: "0", style: { 'background-color': "#f59e0b", color: "#fff" }},
    {text: "Call Clutch", style: { 'background-color': "#059669", color: "#fff" }},
    {text: "Drop", score: "Drop", style: { 'background-color': "#6b7280", color: "#fff" }}
  ]

  const clutchButtons = [
    {text: "Left Clutch", score: "7", style: { 'background-color': "#059669", color: "#fff" }},
    {text: "Right Clutch", score: "7", style: { 'background-color': "#059669", color: "#fff" }},
    {text: "0", score: "0", style: { 'background-color': "#f59e0b", color: "#fff" }},
    {text: "Drop", score: "Drop", style: { 'background-color': "#6b7280", color: "#fff" }},
    {text: "Cancel", style: { 'background-color': "#ef4444", color: "#fff" }}
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

  function urbanScore(score){
    if (score === "Call Clutch") {
      buttons.value = [...clutchButtons]
    } else if (score === "Cancel") {
      buttons.value = [...defaultButtons]
    } else {
      // We look for the 
      const value = buttons.value.find(b => b.text === score)?.score ?? score
      buttons.value = [...defaultButtons]
      emit('score', value)
    }
  }
</script>

<template>
  <div class="grid-container">
    <div v-for="item in displayButtons" class="grid-child">
      <button class="button-circle" :style="item.style" :disabled="props.disabled || (item.text === 'Call Clutch' && !props.clutchAvailable)" @click="urbanScore(item.text)">{{ item.text }}</button>
    </div>
  </div>
</template>

<style>
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
  justify-content: center;
  align-items: center;
  text-align: center;
  width: 125px;
  height: 125px;
  border-radius: 100%;
  background-color: #04AA6D;
  display: flex;
  border: none;
  font-family: inherit;
  font-size: 1.55rem;
  font-weight: bold;
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
</style>
