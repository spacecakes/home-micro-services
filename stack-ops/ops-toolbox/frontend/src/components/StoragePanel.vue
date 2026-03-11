<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'

interface DiskInfo {
  ok: boolean
  total?: number
  used?: number
  free?: number
  error?: string
}

interface StorageResponse {
  host: DiskInfo
  nas: DiskInfo
}

const host = ref<DiskInfo | null>(null)
const nas = ref<DiskInfo | null>(null)

let interval: ReturnType<typeof setInterval> | null = null

function fmt(bytes: number | undefined): string {
  if (!bytes) return '\u2014'
  const gb = bytes / 1073741824
  return gb >= 1000 ? (gb / 1024).toFixed(1) + ' TB' : gb.toFixed(1) + ' GB'
}

function pct(used: number | undefined, total: number | undefined): number {
  if (!used || !total) return 0
  return Math.round((used / total) * 100)
}

function barColor(percent: number): string {
  if (percent >= 90) return 'bg-red-500'
  if (percent >= 75) return 'bg-yellow-500'
  return 'bg-green-500'
}

async function poll(): Promise<void> {
  try {
    const res = await fetch('/api/storage')
    const d: StorageResponse = await res.json()
    host.value = d.host
    nas.value = d.nas
  } catch {
    host.value = { ok: false, error: 'Unreachable' }
    nas.value = { ok: false, error: 'Unreachable' }
  }
}

onMounted(() => {
  poll()
  interval = setInterval(poll, 60000)
})

onUnmounted(() => {
  if (interval) clearInterval(interval)
})
</script>

<template>
  <BaseCard class="col-span-full">
    <h2 class="flex items-center gap-1.5 text-lg font-semibold">
      <Icon icon="lucide:hard-drive" class="h-5 w-5 text-cyan-400" />
      Storage
    </h2>

    <div class="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2">
      <div v-for="(disk, label) in { 'Docker VM': host, 'NAS': nas }" :key="label">
        <div class="flex items-center justify-between text-xs">
          <span class="font-medium text-gray-400">{{ label }}</span>
          <span v-if="disk?.ok" class="tabular-nums text-gray-500">
            {{ fmt(disk.used) }} / {{ fmt(disk.total) }}
          </span>
          <BaseBadge v-else-if="disk" color="red">Offline</BaseBadge>
          <span v-else class="text-gray-600">Loading...</span>
        </div>
        <div class="mt-1 h-2 overflow-hidden rounded-full bg-gray-800">
          <div
            v-if="disk?.ok"
            class="h-full rounded-full transition-all duration-500"
            :class="barColor(pct(disk.used, disk.total))"
            :style="{ width: pct(disk.used, disk.total) + '%' }"
          />
        </div>
        <div v-if="disk?.ok" class="mt-0.5 text-right text-[11px] tabular-nums text-gray-600">
          {{ fmt(disk.free) }} free ({{ pct(disk.used, disk.total) }}% used)
        </div>
      </div>
    </div>
  </BaseCard>
</template>
