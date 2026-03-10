<script setup lang="ts">
import { ref, computed, inject } from 'vue'
import { Icon } from '@iconify/vue'
import type { BackupState } from '../composables/useBackup'

const backup = inject<BackupState>('backup')!

const showModal = ref(false)
const confirmText = ref('')

const dryRun = computed({
  get: () => backup.dryRun.value,
  set: (v: boolean) => { backup.dryRun.value = v },
})

function runBackup(): void {
  backup.runAction('/backup/run')
}

function handleRestore(): void {
  if (backup.dryRun.value) {
    backup.runAction('/backup/restore')
    return
  }
  showModal.value = true
  confirmText.value = ''
}

function doRestore(): void {
  if (confirmText.value.trim() !== 'RESTORE') {
    alert('Please type RESTORE to confirm.')
    return
  }
  showModal.value = false
  backup.runAction('/backup/restore')
}

function timeAgo(iso: string): string {
  if (!iso) return ''
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return Math.floor(s / 60) + 'm ago'
  if (s < 86400) return Math.floor(s / 3600) + 'h ago'
  return Math.floor(s / 86400) + 'd ago'
}
</script>

<template>
  <BaseCard>
    <div>
      <div class="flex flex-wrap items-center gap-2">
        <h2 class="inline-flex items-center gap-1.5 text-lg font-semibold">
          <Icon icon="lucide:hard-drive-download" class="h-5 w-5 text-green-500" />
          Backup & Restore
        </h2>
        <BaseBadge :color="backup.statusColor.value" :pulse="backup.running.value">
          {{ backup.statusText.value }}
        </BaseBadge>
      </div>
      <p v-if="backup.lastBackup.value" class="mt-1.5 flex items-center gap-1 text-xs text-gray-500">
        <Icon icon="lucide:clock" class="h-3 w-3" />
        Last backup: {{ timeAgo(backup.lastBackup.value) }}
      </p>
    </div>

    <div class="mt-3 flex flex-wrap items-center gap-2">
      <BaseButton variant="green" icon="lucide:play" :disabled="backup.running.value" @click="runBackup">
        Run backup
      </BaseButton>
      <BaseButton variant="red" icon="lucide:rotate-ccw" :disabled="backup.running.value" @click="handleRestore">
        Restore
      </BaseButton>
      <label class="flex items-center gap-1 text-xs text-gray-500 cursor-pointer">
        <input type="checkbox" v-model="dryRun" :disabled="backup.running.value" class="accent-gray-500">
        Dry run
      </label>
    </div>

    <!-- Restore confirmation modal -->
    <Teleport to="body">
      <div v-if="showModal" class="fixed inset-0 z-50 flex items-start justify-center bg-black/70 pt-[15vh]" @click.self="showModal = false">
        <div class="w-full max-w-md rounded-xl border border-gray-700 bg-gray-900 p-5 shadow-lg">
          <h2 class="mb-3 flex items-center gap-2 text-lg font-semibold text-red-400">
            <Icon icon="lucide:alert-triangle" class="h-5 w-5" />
            Restore from NAS backup
          </h2>
          <div class="mb-3 rounded-lg border border-red-800/60 bg-red-950/30 p-3 text-xs leading-relaxed text-red-300/80">
            This will stop all running Docker containers (except ops-toolbox),
            then rsync from the NAS backup back to /srv/docker. Use "Start all" afterwards to bring stacks back up.
          </div>
          <p class="mb-2 text-sm">Type <strong class="text-white">RESTORE</strong> to confirm:</p>
          <input
            v-model="confirmText"
            type="text"
            placeholder="Type RESTORE"
            autocomplete="off"
            class="mb-3 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-300 outline-none focus:border-gray-500"
            @keyup.enter="doRestore"
          >
          <div class="flex justify-end gap-2">
            <BaseButton icon="lucide:x" @click="showModal = false">Cancel</BaseButton>
            <BaseButton variant="red" icon="lucide:rotate-ccw" @click="doRestore">Restore</BaseButton>
          </div>
        </div>
      </div>
    </Teleport>
  </BaseCard>
</template>
