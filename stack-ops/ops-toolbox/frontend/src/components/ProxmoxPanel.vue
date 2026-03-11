<script setup lang="ts">
import { computed, inject } from 'vue'
import { Icon } from '@iconify/vue'
import type { BackupState } from '../composables/useBackup'
import { timeAgo } from '../utils'

const backup = inject<BackupState>('backup')!

const isPveAction = computed(() => backup.action.value.includes('pve'))
</script>

<template>
  <BaseCard>
    <div>
      <div class="flex flex-wrap items-center gap-2">
        <h2 class="inline-flex items-center gap-1.5 text-lg font-semibold">
          <Icon icon="lucide:server" class="h-5 w-5 text-purple-400" />
          Proxmox Backup
        </h2>
        <BaseBadge v-if="isPveAction" color="yellow" :pulse="true">
          {{ backup.statusText.value }}
        </BaseBadge>
      </div>
      <p class="mt-1.5 text-xs text-gray-500">
        Daily rsync of /etc/pve to NAS.
        <span v-if="backup.lastPveBackup.value" class="inline-flex items-center gap-1">
          <Icon icon="lucide:clock" class="h-3 w-3" />
          Last: {{ timeAgo(backup.lastPveBackup.value) }}
        </span>
      </p>
    </div>
    <div class="mt-3">
      <BaseButton variant="green" icon="lucide:play" :disabled="backup.running.value" :loading="isPveAction" @click="backup.runAction('/proxmox/run')">
        Run backup
      </BaseButton>
    </div>
  </BaseCard>
</template>
