<script setup lang="ts">
import { inject } from 'vue'
import { Icon } from '@iconify/vue'
import type { BackupState } from '../composables/useBackup'

const backup = inject<BackupState>('backup')!
</script>

<template>
  <BaseCard>
    <h2 class="flex items-center gap-1.5 text-lg font-semibold">
      <Icon icon="lucide:boxes" class="h-5 w-5 text-blue-400" />
      Container Control
    </h2>
    <p class="mt-1.5 text-xs text-gray-500">Stop or start all Docker stacks (except ops-toolbox).</p>
    <div class="mt-3 flex flex-wrap items-center gap-2">
      <BaseButton
        variant="yellow"
        icon="lucide:square"
        :disabled="backup.running.value"
        @click="backup.runAction('/containers/stop-all')"
      >
        Stop all
      </BaseButton>
      <BaseButton
        variant="blue"
        icon="lucide:play"
        :disabled="backup.running.value"
        @click="backup.runAction('/containers/start-all')"
      >
        Start all
      </BaseButton>
    </div>
  </BaseCard>
</template>
