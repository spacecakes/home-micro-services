<script setup lang="ts">
import { provide } from 'vue'
import { Icon } from '@iconify/vue'
import { useBackup } from './composables/useBackup'
import UpsPanel from './components/UpsPanel.vue'
import BackupPanel from './components/BackupPanel.vue'
import ContainerPanel from './components/ContainerPanel.vue'
import ActivityLog from './components/ActivityLog.vue'

const backup = useBackup()
provide('backup', backup)
</script>

<template>
  <h1 class="mb-5 flex items-center gap-2.5 text-xl font-bold tracking-tight">
    <Icon icon="lucide:layout-dashboard" class="h-6 w-6 text-gray-500" />
    Ops Dashboard
  </h1>
  <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
    <UpsPanel title="Rack UPS" api-url="/api/ups" :show-shutdown="true" />
    <UpsPanel title="Desktop UPS" api-url="/api/ups2" />
    <BackupPanel />
    <ContainerPanel />
    <ActivityLog />
  </div>
</template>
