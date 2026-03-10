<script setup lang="ts">
import { inject, ref, watch, nextTick } from 'vue'
import { Icon } from '@iconify/vue'
import type { BackupState } from '../composables/useBackup'

const backup = inject<BackupState>('backup')!
const logEl = ref<HTMLPreElement | null>(null)

watch(() => backup.log.value, async () => {
  await nextTick()
  if (!logEl.value) return
  const el = logEl.value
  const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 50
  if (atBottom) el.scrollTop = el.scrollHeight
})

async function clearLog(): Promise<void> {
  await fetch('/backup/clear-log', { method: 'POST' })
  backup.poll()
}
</script>

<template>
  <BaseCard class="col-span-full">
    <div class="flex items-center justify-between">
      <h2 class="flex items-center gap-1.5 text-lg font-semibold">
        <Icon icon="lucide:scroll-text" class="h-5 w-5 text-gray-500" />
        Activity Log
      </h2>
      <BaseButton icon="lucide:trash-2" @click="clearLog">Clear</BaseButton>
    </div>
    <pre
      ref="logEl"
      class="mt-3 max-h-[55vh] overflow-auto whitespace-pre-wrap rounded-lg border border-gray-800 bg-gray-950/60 p-4 font-mono text-xs leading-relaxed text-gray-400"
    >{{ backup.log.value || 'No activity yet.' }}</pre>
  </BaseCard>
</template>
