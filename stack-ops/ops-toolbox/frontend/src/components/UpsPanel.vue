<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Icon } from '@iconify/vue'

interface UpsData {
  STATUS?: string
  MODEL?: string
  LASTXFER?: string
  [key: string]: string | undefined
}

interface UpsResponse {
  ok: boolean
  data?: UpsData
  error?: string
}

interface ShutdownResult {
  ok: boolean
  message: string
}

interface Metric {
  label: string
  key: string
  suffix: string
  icon: string
}

const props = withDefaults(defineProps<{
  title: string
  apiUrl: string
  showShutdown?: boolean
}>(), {
  showShutdown: false,
})

const data = ref<UpsData | null>(null)
const error = ref(false)

const shutdownLoading = ref(false)
const shutdownResult = ref<ShutdownResult | null>(null)

let interval: ReturnType<typeof setInterval> | null = null

function stripUnit(val: string | undefined): string {
  if (!val) return '\u2014'
  return val.replace(/ (Percent|Volts|Minutes|Seconds|Hz|Watts|VA)$/i, '').trim()
}

function badgeColor(status: string | undefined): 'green' | 'red' | 'yellow' | 'gray' {
  if (!status) return 'gray'
  if (status.includes('ONLINE')) return 'green'
  if (status.includes('ONBATT')) return 'red'
  return 'yellow'
}

async function poll(): Promise<void> {
  try {
    const res = await fetch(props.apiUrl)
    const json: UpsResponse = await res.json()
    if (json.ok && json.data) {
      data.value = json.data
      error.value = false
    } else {
      data.value = null
      error.value = true
    }
  } catch {
    data.value = null
    error.value = true
  }
}

async function testShutdown(): Promise<void> {
  shutdownLoading.value = true
  shutdownResult.value = null
  try {
    const res = await fetch('/api/test-shutdown', { method: 'POST' })
    shutdownResult.value = await res.json()
  } catch {
    shutdownResult.value = { ok: false, message: 'Request error' }
  } finally {
    shutdownLoading.value = false
  }
}

const metrics: Metric[] = [
  { label: 'Load', key: 'LOADPCT', suffix: '%', icon: 'lucide:gauge' },
  { label: 'Battery', key: 'BCHARGE', suffix: '%', icon: 'lucide:battery-charging' },
  { label: 'Runtime', key: 'TIMELEFT', suffix: ' min', icon: 'lucide:clock' },
  { label: 'Line voltage', key: 'LINEV', suffix: ' V', icon: 'lucide:plug' },
  { label: 'Temperature', key: 'ITEMP', suffix: '\u00b0C', icon: 'lucide:thermometer' },
  { label: 'Output voltage', key: 'OUTPUTV', suffix: ' V', icon: 'lucide:zap' },
]

onMounted(() => {
  poll()
  interval = setInterval(poll, 30000)
})

onUnmounted(() => {
  if (interval) clearInterval(interval)
})
</script>

<template>
  <BaseCard>
    <div class="mb-1">
      <div class="flex flex-wrap items-center gap-2">
        <h2 class="inline-flex items-center gap-1.5 text-lg font-semibold">
          <Icon icon="lucide:zap" class="h-5 w-5 text-yellow-500" />
          {{ title }}
        </h2>
        <BaseBadge :color="error ? 'gray' : badgeColor(data?.STATUS)">
          {{ error ? 'Offline' : (data?.STATUS || 'Loading...') }}
        </BaseBadge>
      </div>
      <p v-if="data?.MODEL" class="mt-1.5 text-xs text-gray-500">{{ data.MODEL }}</p>
    </div>

    <div class="my-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
      <div
        v-for="m in metrics"
        :key="m.key"
        class="rounded-lg border border-gray-800 bg-gray-950/60 px-3 py-2.5 transition-colors hover:border-gray-700"
      >
        <div class="flex items-center gap-1 text-[11px] text-gray-500">
          <Icon :icon="m.icon" class="h-3 w-3 shrink-0" />
          {{ m.label }}
        </div>
        <div class="mt-0.5 text-lg font-semibold tabular-nums tracking-tight">
          {{ data ? stripUnit(data[m.key]) + m.suffix : '\u2014' }}
        </div>
      </div>
    </div>

    <p v-if="data?.LASTXFER" class="flex items-center gap-1 text-xs text-gray-500">
      <Icon icon="lucide:arrow-right-left" class="h-3 w-3" />
      Last transfer: {{ data.LASTXFER }}
    </p>

    <div v-if="showShutdown" class="mt-3 flex items-center gap-3">
      <BaseButton icon="lucide:power" :disabled="shutdownLoading" @click="testShutdown">
        Test shutdown path
        <span v-if="shutdownLoading" class="ml-1 inline-block h-3 w-3 animate-spin rounded-full border-2 border-gray-500 border-t-white align-middle" />
      </BaseButton>
      <span
        v-if="shutdownResult"
        class="text-xs"
        :class="shutdownResult.ok ? 'text-green-400' : 'text-red-400'"
      >
        {{ shutdownResult.ok ? 'OK' : 'FAIL' }} &mdash; {{ shutdownResult.message }}
      </span>
    </div>

    <details class="group mt-3">
      <summary class="flex cursor-pointer items-center gap-1 text-xs text-gray-500 select-none hover:text-gray-400">
        <Icon icon="lucide:chevron-right" class="h-3 w-3 transition-transform group-open:rotate-90" />
        Show raw output
      </summary>
      <div v-if="data" class="mt-2 overflow-hidden rounded-md border border-gray-800">
        <table class="w-full text-xs">
          <tr
            v-for="(val, key) in data"
            :key="key"
            class="border-b border-gray-800/50 last:border-0 even:bg-gray-900/40"
          >
            <td class="w-2/5 px-3 py-1.5 font-medium text-gray-500">{{ key }}</td>
            <td class="px-3 py-1.5 tabular-nums">{{ val }}</td>
          </tr>
        </table>
      </div>
    </details>
  </BaseCard>
</template>
