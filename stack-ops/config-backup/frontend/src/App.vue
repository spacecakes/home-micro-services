<script setup lang="ts">
import { provide } from 'vue'
import { Icon } from '@iconify/vue'
import { useBackup } from './composables/useBackup'
import ConfigBackupPanel from './components/ConfigBackupPanel.vue'

const backup = useBackup()
provide('backup', backup)
</script>

<template>
  <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
    <h1 class="flex items-center gap-2.5 text-xl font-bold tracking-tight">
      <Icon icon="lucide:shield-check" class="h-6 w-6 text-purple-400" />
      Config Backup
    </h1>
    <div class="flex items-center gap-3">
      <BaseBadge :color="backup.statusColor.value" :pulse="backup.running.value">
        {{ backup.statusText.value }}
      </BaseBadge>
      <label class="flex items-center gap-1.5 text-xs text-gray-500 cursor-pointer select-none">
        <input type="checkbox" :checked="backup.dryRun.value" :disabled="backup.running.value" class="accent-gray-500" @change="backup.dryRun.value = ($event.target as HTMLInputElement).checked">
        Dry run
      </label>
    </div>
  </div>
  <ConfigBackupPanel />
</template>
