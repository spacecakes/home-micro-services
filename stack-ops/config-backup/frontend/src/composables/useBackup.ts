import { ref, computed, onMounted, onUnmounted } from 'vue'
import type { Ref, ComputedRef } from 'vue'

type BadgeColor = 'green' | 'red' | 'yellow' | 'gray'

interface StatusResponse {
  running: boolean
  action: string
  log: string
  last_backup: string | null
  last_error: string | null
}

export interface BackupState {
  running: Ref<boolean>
  action: Ref<string>
  log: Ref<string>
  lastBackup: Ref<string>
  lastError: Ref<string>
  dryRun: Ref<boolean>
  statusText: ComputedRef<string>
  statusColor: ComputedRef<BadgeColor>
  runAction: (url: string) => void
  poll: () => Promise<void>
}

export function useBackup(): BackupState {
  const running = ref(false)
  const action = ref('')
  const log = ref('')
  const lastBackup = ref('')
  const lastError = ref('')
  const dryRun = ref(false)
  const fails = ref(0)

  let pollTimer: ReturnType<typeof setTimeout> | null = null

  const statusText = computed((): string => {
    if (fails.value >= 3) return 'Unreachable'
    if (!running.value) return lastError.value ? 'Last run failed' : 'Idle'
    const a = action.value
    const isDry = a.includes('dry')
    return isDry ? 'Backup dry-run...' : 'Backing up...'
  })

  const statusColor = computed((): BadgeColor => {
    if (fails.value >= 3) return 'red'
    if (!running.value) return lastError.value ? 'red' : 'green'
    return 'yellow'
  })

  async function poll(): Promise<void> {
    try {
      const res = await fetch('/api/status')
      if (!res.ok) throw new Error()
      const d: StatusResponse = await res.json()
      fails.value = 0
      running.value = d.running
      action.value = d.action || ''
      log.value = d.log || ''
      lastBackup.value = d.last_backup || ''
      lastError.value = d.last_error || ''
    } catch {
      fails.value++
      if (fails.value >= 3) {
        log.value = 'Error: config-backup container is not reachable. Polling stopped \u2014 reload page to retry.'
      } else {
        log.value = 'Error: config-backup container is not reachable. Retrying...'
      }
    }
  }

  function schedule(): void {
    if (fails.value >= 3) return
    pollTimer = setTimeout(async () => {
      await poll()
      schedule()
    }, running.value ? 2000 : 15000)
  }

  function runAction(url: string): void {
    let u = url
    if (dryRun.value) u += (u.includes('?') ? '&' : '?') + 'dry=1'
    running.value = true
    fetch(u, { method: 'POST' })
      .catch(() => {})
      .finally(() => {
        if (pollTimer) clearTimeout(pollTimer)
        poll().then(schedule)
      })
  }

  onMounted(() => {
    poll()
    schedule()
  })

  onUnmounted(() => {
    if (pollTimer) clearTimeout(pollTimer)
  })

  return {
    running,
    action,
    log,
    lastBackup,
    lastError,
    dryRun,
    statusText,
    statusColor,
    runAction,
    poll,
  }
}
