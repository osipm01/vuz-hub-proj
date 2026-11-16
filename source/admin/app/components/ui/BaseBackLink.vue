<template>
  <div class="navigation-bar">
    <NuxtLink :to="to" class="btn-back">
      <slot>{{ label }}</slot>
    </NuxtLink>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  to: string
  label?: string
}>(), {
  label: '← Назад',
})
</script>

<style scoped>
.navigation-bar {
  margin-bottom: 16px;
  display: flex;
  justify-content: flex-start;
}

.btn-back {
  color: rgba(255, 255, 255, 0.7);
  text-decoration: none;
  font-size: 14px;
  transition: color 0.2s;
}

.btn-back:hover {
  color: #ffffff;
}
</style>