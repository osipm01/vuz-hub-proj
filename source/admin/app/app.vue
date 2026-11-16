<script setup lang="ts">
import { ref } from 'vue'

const layout = ref<'default' | 'custom'>('default')
</script>

<template>
  <NuxtLayout>
    <NuxtPage />
  </NuxtLayout>
</template>
