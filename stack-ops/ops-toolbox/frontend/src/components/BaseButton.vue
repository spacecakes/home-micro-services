<script setup lang="ts">
import { Icon } from '@iconify/vue'

withDefaults(defineProps<{
  variant?: 'ghost' | 'green' | 'red' | 'yellow' | 'blue'
  disabled?: boolean
  icon?: string
  loading?: boolean
}>(), {
  variant: 'ghost',
  disabled: false,
  icon: '',
  loading: false,
})

const colors: Record<string, string> = {
  green: 'bg-green-700 hover:bg-green-600 active:bg-green-800',
  red: 'bg-red-700 hover:bg-red-600 active:bg-red-800',
  yellow: 'bg-yellow-600 hover:bg-yellow-500 active:bg-yellow-700',
  blue: 'bg-blue-600 hover:bg-blue-500 active:bg-blue-700',
}
</script>

<template>
  <button
    v-if="variant === 'ghost'"
    class="inline-flex items-center gap-1.5 rounded-md border border-gray-700 px-3 py-1.5 text-xs font-medium text-gray-400 transition-colors hover:border-gray-500 hover:text-gray-200 active:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-50"
    :disabled="disabled"
    v-bind="$attrs"
  >
    <Icon v-if="icon && !loading" :icon="icon" class="h-3.5 w-3.5" />
    <Icon v-else-if="loading" icon="lucide:loader-2" class="h-3.5 w-3.5 animate-spin" />
    <slot />
  </button>
  <button
    v-else
    class="inline-flex items-center gap-1.5 rounded-md px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors disabled:cursor-not-allowed disabled:bg-gray-700 disabled:text-gray-500"
    :class="colors[variant]"
    :disabled="disabled"
    v-bind="$attrs"
  >
    <Icon v-if="icon && !loading" :icon="icon" class="h-4 w-4" />
    <Icon v-else-if="loading" icon="lucide:loader-2" class="h-4 w-4 animate-spin" />
    <slot />
  </button>
</template>
