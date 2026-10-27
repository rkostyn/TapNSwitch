<script setup>
  import { arenaById } from '../venue'

  defineProps({
    arenaIds: { type: Array, default: () => [] },
  })
</script>

<template>
  <span v-if="arenaIds?.length" class="arena-chip-row">
    <span
      v-for="id in arenaIds"
      :key="id"
      class="arena-chip"
      :style="{ background: arenaById(id)?.color, color: arenaById(id)?.text_color }"
    >{{ arenaById(id)?.name ?? id }}</span>
  </span>
</template>
