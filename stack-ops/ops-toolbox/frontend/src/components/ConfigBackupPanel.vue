<script setup lang="ts">
import { computed, inject, ref, watch, nextTick, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import type { BackupState } from '../composables/useBackup'
import { timeAgo } from '../utils'

const backup = inject<BackupState>('backup')!

const isRunning = computed(() => backup.action.value.includes('config-backup'))
const logEl = ref<HTMLDivElement | null>(null)

interface Target {
  name: string
  icon: string
  detail: string
  items: string[]
  dest: string
}

const targets = ref<Target[]>([])

onMounted(async () => {
  try {
    const res = await fetch('/api/targets')
    const d = await res.json()
    targets.value = d.targets
  } catch { /* ignore */ }
})

const iconMap: Record<string, string> = {
  pve: 'lucide:server',
  ups: 'lucide:zap',
}

function lineClass(line: string): string {
  if (line.includes('FAILED') || line.includes('error:') || line.includes('rsync error'))
    return 'text-red-400'
  if (line.includes('completed at'))
    return 'text-green-400'
  if (line.startsWith('===='))
    return 'text-gray-300 font-semibold'
  if (line.startsWith('['))
    return 'text-purple-400 font-medium'
  if (line.startsWith('    OK'))
    return 'text-green-500'
  return ''
}

const logLines = computed(() => {
  if (!backup.log.value) return []
  return backup.log.value.split('\n')
})

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
    <div>
      <div class="flex flex-wrap items-center gap-2">
        <h2 class="inline-flex items-center gap-1.5 text-lg font-semibold">
          <Icon icon="lucide:shield-check" class="h-5 w-5 text-purple-400" />
          Config Backup
        </h2>
        <BaseBadge v-if="isRunning" color="yellow" :pulse="true">
          {{ backup.statusText.value }}
        </BaseBadge>
      </div>
      <p class="mt-1.5 text-xs text-gray-500">
        Daily backup of infrastructure config to NAS.
        <span v-if="backup.lastBackup.value" class="inline-flex items-center gap-1">
          <Icon icon="lucide:clock" class="h-3 w-3" />
          Last: {{ timeAgo(backup.lastBackup.value) }}
        </span>
      </p>
    </div>

    <!-- Backup targets -->
    <div v-if="targets.length" class="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
      <div
        v-for="t in targets"
        :key="t.name"
        class="rounded-lg border border-gray-800 bg-gray-950/60 px-3 py-2.5"
      >
        <div class="flex items-center gap-1.5 text-xs font-medium text-gray-400">
          <Icon :icon="iconMap[t.icon] || 'lucide:folder'" class="h-3.5 w-3.5 shrink-0" />
          {{ t.name }}
          <span class="ml-auto text-gray-600">{{ t.detail }}</span>
        </div>
        <div class="mt-1.5 flex flex-wrap gap-1">
          <span
            v-for="item in t.items"
            :key="item"
            class="rounded bg-gray-800 px-1.5 py-0.5 text-[11px] tabular-nums text-gray-500"
          >{{ item }}</span>
        </div>
        <div class="mt-1.5 text-[11px] text-gray-600">
          &rarr; {{ t.dest }}/
        </div>
      </div>
    </div>

    <div class="mt-3 flex items-center gap-2">
      <BaseButton variant="green" icon="lucide:play" :disabled="backup.running.value" :loading="isRunning" @click="backup.runAction('/backup/run')">
        Run backup
      </BaseButton>
      <BaseButton icon="lucide:trash-2" @click="clearLog">Clear log</BaseButton>
    </div>
    <div
      ref="logEl"
      class="mt-3 max-h-[55vh] overflow-auto whitespace-pre-wrap rounded-lg border border-gray-800 bg-gray-950/60 p-4 font-mono text-xs leading-relaxed text-gray-400"
    >
      <template v-if="logLines.length">
        <div v-for="(line, i) in logLines" :key="i" :class="lineClass(line)">{{ line }}</div>
      </template>
      <span v-else class="text-gray-600">No activity yet.</span>
    </div>
  </BaseCard>
</template>
