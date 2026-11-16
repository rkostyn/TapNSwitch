<script setup lang="ts">
  import { arenaById } from '../venue'

  withDefaults(defineProps<{ arenaIds?: string[] | null }>(), {
    arenaIds: () => [],
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
