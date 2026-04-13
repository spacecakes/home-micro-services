<script setup lang="ts">
defineProps<{
  color?: 'green' | 'red' | 'yellow' | 'gray'
  pulse?: boolean
}>()

const colors: Record<string, string> = {
  green: 'bg-green-600/90',
  red: 'bg-red-600/90',
  yellow: 'bg-yellow-600/90',
  gray: 'bg-gray-600/90',
}
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium text-white transition-colors"
    :class="colors[color ?? 'gray']"
  >
    <span
      v-if="pulse"
      class="h-1.5 w-1.5 rounded-full bg-current animate-pulse"
    />
    <slot />
  </span>
</template>
